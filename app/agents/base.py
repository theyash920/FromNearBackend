from __future__ import annotations

from typing import Any

from app.agents.state import GrowthState
from app.schemas import AgentEvent
from app.services.events import WorkflowEventBus
from app.services.llm import LocalLLMClient


class AgentBase:
    """Base class for all worker agents.

    Provides:
    - Token-efficient prompt building via build_compact_prompt()
    - Response wrapping in the structured AgentResponse format
    - Event emission for real-time UI updates
    - Reasoning trace logging
    """

    name = "agent"
    max_context_window: int = 3  # Configurable per agent subclass

    def __init__(self, llm: LocalLLMClient | None = None, event_bus: WorkflowEventBus | None = None):
        self.llm = llm or LocalLLMClient()
        self.event_bus = event_bus or WorkflowEventBus()

    async def emit(self, state: GrowthState, message: str, payload: dict | None = None) -> None:
        run_id = state.get("run_id")
        if not run_id:
            return
        await self.event_bus.publish(
            AgentEvent(
                run_id=run_id,
                status="running",
                agent=self.name,
                message=message,
                payload=payload or {},
            )
        )

    def trace(self, state: GrowthState, message: str) -> None:
        state.setdefault("reasoning_trace", []).append(f"{self.name}: {message}")

    def build_compact_prompt(
        self,
        state: GrowthState,
        task_description: str,
        relevant_data: dict[str, Any],
    ) -> str:
        """Build a token-efficient prompt by including only relevant data.

        Instead of dumping the entire state dict (~thousands of tokens),
        this method:
        1. Injects recovered memory summary (if available)
        2. Includes only the data keys the specific agent needs
        3. Keeps the total prompt compact
        """
        parts: list[str] = []

        # Inject recovered memory if available (from controller pipeline)
        recovered_memory = state.get("_recovered_memory")
        if recovered_memory:
            parts.append(recovered_memory)
            parts.append("")

        # Task description
        parts.append(f"Task: {task_description}")
        parts.append("")

        # Only include relevant data, truncating large values
        for key, value in relevant_data.items():
            val_str = str(value)
            if len(val_str) > 500:
                val_str = val_str[:500] + "...(truncated)"
            parts.append(f"{key}: {val_str}")

        return "\n".join(parts)

    def compact_dict(self, data: dict[str, Any], max_keys: int = 10) -> dict[str, Any]:
        """Truncate a dictionary to keep only the most important keys."""
        if len(data) <= max_keys:
            return data
        return dict(list(data.items())[:max_keys])
