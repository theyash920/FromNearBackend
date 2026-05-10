"""Memory extraction, injection, and persistence for token-efficient agents.

Implements the hybrid memory architecture:
- MySQL: long-term persistent storage (conversations, memory snapshots, audit)
- In-memory dict: ephemeral short-term session state for the current process

The memory pipeline:
1. Scan backward through message history
2. Find the MOST RECENT assistant message containing a memory object
3. Extract the memory/state dictionary
4. Convert it into a compact summary string
5. Inject it dynamically into the system prompt
"""

from __future__ import annotations

import json
from typing import Any

from app.schemas.response_schemas import AgentMemory


# ---------------------------------------------------------------------------
# Memory extraction from message history
# ---------------------------------------------------------------------------

def extract_memory(messages: list[dict[str, Any]]) -> AgentMemory | None:
    """Iterate backward through messages and find the most recent memory object.

    Scans assistant messages for a JSON body containing a 'memory' key.
    Returns None if no memory is found (first turn of conversation).
    """
    for msg in reversed(messages):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
            if isinstance(parsed, dict) and "memory" in parsed:
                return AgentMemory.model_validate(parsed["memory"])
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return None


def format_memory_prompt(memory: AgentMemory | None) -> str:
    """Convert a memory object into a compact bullet-point summary for injection.

    This is what gets added to the system prompt so the agent has context
    without receiving the full conversation history.
    """
    if memory is None:
        return "No prior conversation memory available. This is the first interaction."

    lines = ["Recovered conversation memory:"]
    lines.append(f"  - active_agent: {memory.active_agent}")
    lines.append(f"  - step: {memory.step}")

    if memory.vendor_context:
        for key, value in memory.vendor_context.items():
            lines.append(f"  - vendor.{key}: {value}")

    if memory.workflow_progress:
        lines.append(f"  - completed_stages: {', '.join(memory.workflow_progress)}")

    if memory.pending_actions:
        lines.append(f"  - pending: {', '.join(memory.pending_actions)}")

    if memory.accumulated_data:
        for key, value in memory.accumulated_data.items():
            # Truncate large values to keep the prompt compact
            val_str = str(value)
            if len(val_str) > 200:
                val_str = val_str[:200] + "..."
            lines.append(f"  - data.{key}: {val_str}")

    return "\n".join(lines)


def merge_memory(old: AgentMemory | None, new_data: dict[str, Any]) -> AgentMemory:
    """Merge new agent output data into existing memory, preserving history."""
    base = old.model_dump() if old else AgentMemory().model_dump()

    # Update active agent
    if "active_agent" in new_data:
        base["active_agent"] = new_data["active_agent"]

    # Increment step
    base["step"] = base.get("step", 0) + 1

    # Merge vendor context
    if "vendor_context" in new_data:
        base.setdefault("vendor_context", {}).update(new_data["vendor_context"])

    # Append workflow progress
    if "completed_stage" in new_data:
        base.setdefault("workflow_progress", []).append(new_data["completed_stage"])

    # Merge accumulated data
    if "accumulated_data" in new_data:
        base.setdefault("accumulated_data", {}).update(new_data["accumulated_data"])

    # Set pending actions
    if "pending_actions" in new_data:
        base["pending_actions"] = new_data["pending_actions"]

    return AgentMemory.model_validate(base)


# ---------------------------------------------------------------------------
# MySQL-backed session memory (replaces Redis)
# ---------------------------------------------------------------------------

class SessionMemoryStore:
    """MySQL-backed session state for active workflows via the conversations table.

    Uses a local in-memory dictionary as a fast cache that is also persisted
    to the MySQL `conversations` table for durability across restarts.

    TTL is not enforced at this layer; the conversations table keeps history.
    """

    _LOCAL_CACHE: dict[str, str] = {}  # Fast in-process cache

    def __init__(self) -> None:
        pass

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def save_session(self, session_id: str, data: dict[str, Any]) -> None:
        """Save session state to in-memory cache (persisted to MySQL by controller)."""
        self._LOCAL_CACHE[self._key(session_id)] = json.dumps(data)

    async def load_session(self, session_id: str) -> dict[str, Any] | None:
        """Load session state from in-memory cache, or from MySQL conversations table."""
        raw = self._LOCAL_CACHE.get(self._key(session_id))
        if raw:
            return json.loads(raw)

        # Try to recover from MySQL conversations table
        try:
            from app.db.session import AsyncSessionLocal
            from app.models import Conversation
            from sqlalchemy import select

            async with AsyncSessionLocal() as db_session:
                result = await db_session.execute(
                    select(Conversation)
                    .where(Conversation.session_id == session_id)
                    .order_by(Conversation.updated_at.desc())
                    .limit(1)
                )
                conversation = result.scalar_one_or_none()
                if conversation and conversation.memory_snapshot:
                    session_data = {
                        "memory_snapshot": conversation.memory_snapshot,
                        "active_agent": conversation.memory_snapshot.get("active_agent", "router"),
                    }
                    self._LOCAL_CACHE[self._key(session_id)] = json.dumps(session_data)
                    return session_data
        except Exception:
            pass

        return None

    async def update_active_agent(self, session_id: str, agent_name: str) -> None:
        """Update the currently active agent for a session."""
        session = await self.load_session(session_id) or {}
        session["active_agent"] = agent_name
        await self.save_session(session_id, session)

    async def cache_recent_context(
        self, session_id: str, messages: list[dict[str, Any]], memory: dict[str, Any]
    ) -> None:
        """Cache the recent context window and memory snapshot."""
        session = await self.load_session(session_id) or {}
        session["recent_messages"] = messages[-4:]  # Keep last 4 messages
        session["memory_snapshot"] = memory
        await self.save_session(session_id, session)

    async def delete_session(self, session_id: str) -> None:
        """Remove session state from cache."""
        self._LOCAL_CACHE.pop(self._key(session_id), None)
