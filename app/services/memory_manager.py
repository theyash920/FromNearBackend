"""Memory extraction, injection, and persistence for token-efficient agents.

Implements the hybrid memory architecture:
- Redis: ephemeral short-term session state (active agent, recent context, temp cache)
- MySQL: long-term persistent storage (conversations, memory snapshots, audit)

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

import redis.asyncio as aioredis

from app.core.config import get_settings
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
# Redis: ephemeral short-term session memory
# ---------------------------------------------------------------------------

class SessionMemoryStore:
    """Redis-backed ephemeral session state for active workflows.

    Stores:
    - Current active agent for the session
    - Recent context window (last 3-4 messages)
    - Temporary workflow cache
    - Realtime session handling state

    TTL: 1 hour (sessions expire after inactivity).
    """

    TTL_SECONDS = 3600  # 1 hour

    def __init__(self) -> None:
        self.settings = get_settings()

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def save_session(self, session_id: str, data: dict[str, Any]) -> None:
        """Save ephemeral session state to Redis with TTL."""
        client = aioredis.from_url(self.settings.redis_url, decode_responses=True)
        try:
            await client.setex(self._key(session_id), self.TTL_SECONDS, json.dumps(data))
        finally:
            await client.aclose()

    async def load_session(self, session_id: str) -> dict[str, Any] | None:
        """Load ephemeral session state from Redis."""
        client = aioredis.from_url(self.settings.redis_url, decode_responses=True)
        try:
            raw = await client.get(self._key(session_id))
            return json.loads(raw) if raw else None
        finally:
            await client.aclose()

    async def update_active_agent(self, session_id: str, agent_name: str) -> None:
        """Update the currently active agent for a session."""
        session = await self.load_session(session_id) or {}
        session["active_agent"] = agent_name
        await self.save_session(session_id, session)

    async def cache_recent_context(
        self, session_id: str, messages: list[dict[str, Any]], memory: dict[str, Any]
    ) -> None:
        """Cache the recent context window and memory snapshot in Redis."""
        session = await self.load_session(session_id) or {}
        session["recent_messages"] = messages[-4:]  # Keep last 4 messages
        session["memory_snapshot"] = memory
        await self.save_session(session_id, session)

    async def delete_session(self, session_id: str) -> None:
        """Remove session state from Redis."""
        client = aioredis.from_url(self.settings.redis_url, decode_responses=True)
        try:
            await client.delete(self._key(session_id))
        finally:
            await client.aclose()
