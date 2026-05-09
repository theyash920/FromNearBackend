"""Pydantic schemas for the token-efficient agent response system."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentMemory(BaseModel):
    """Hidden state persisted across turns. Never sent raw to the LLM.

    Instead, this is extracted from the most recent assistant response,
    compressed into a bullet-point summary, and injected into the system prompt.
    """

    active_agent: str = "router"
    step: int = 0
    vendor_context: dict[str, Any] = Field(default_factory=dict)
    workflow_progress: list[str] = Field(default_factory=list)
    accumulated_data: dict[str, Any] = Field(default_factory=dict)
    pending_actions: list[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    """Every agent MUST return this structure. The frontend renders `response`
    and ignores `memory`. The backend persists `memory` for future turns."""

    response: dict[str, Any]
    memory: AgentMemory


class ChatMessage(BaseModel):
    """A single message in the conversation history."""

    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Inbound request to the /chat endpoint."""

    messages: list[ChatMessage]
    vendor_context: dict[str, Any] | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Outbound response from the /chat endpoint."""

    response: dict[str, Any]
    memory: AgentMemory
    routed_to: str
    session_id: str


class RouteDecision(BaseModel):
    """Output from the lightweight router/classifier agent."""

    route: Literal[
        "research_agent",
        "qualification_agent",
        "sales_agent",
        "marketing_agent",
        "validator_agent",
        "full_pipeline",
    ]
    reasoning: str = ""
