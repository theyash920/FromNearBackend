"""Lightweight router/classifier agent for token-efficient routing.

This agent inspects ONLY the latest user message + last 2 messages
and determines which worker agent (or full pipeline) is needed.

It uses a minimal system prompt (~200 tokens) for maximum efficiency.
"""

from __future__ import annotations

import json

from app.schemas.response_schemas import AgentMemory, RouteDecision
from app.services.context_window import truncate_messages
from app.services.llm import LocalLLMClient
from app.services.memory_manager import format_memory_prompt


class RouterAgent:
    """Ultra-lightweight classifier that routes to the correct worker agent.

    Token budget: ~300 tokens total (system + user prompt).
    Does NOT use tools, memory writes, or heavy context.
    """

    name = "router_agent"

    SYSTEM_PROMPT = (
        "You are a routing classifier for FromNear's AI Growth Employee.\n"
        "Your ONLY job is to decide which agent should handle the user's request.\n\n"
        "Available routes:\n"
        "- research_agent: website/Instagram/business research and analysis\n"
        "- qualification_agent: lead scoring, pain points, revenue estimation\n"
        "- sales_agent: outreach, pitches, follow-ups, objection handling\n"
        "- marketing_agent: campaigns, Instagram posts, reels, hooks, captions\n"
        "- validator_agent: validate or fix existing output JSON\n"
        "- full_pipeline: complex tasks needing multiple agents sequentially\n\n"
        "Return ONLY valid JSON: {\"route\": \"<agent_name>\", \"reasoning\": \"<brief>\"}\n"
    )

    def __init__(self, llm: LocalLLMClient | None = None):
        self.llm = llm or LocalLLMClient()

    async def classify(
        self,
        messages: list[dict],
        recovered_memory: AgentMemory | None = None,
    ) -> RouteDecision:
        """Classify the user's intent and return a routing decision.

        Uses only the last 2 messages + memory summary for minimal token usage.
        """
        # Truncate to absolute minimum for classification
        recent = truncate_messages(messages, window_size=2, preserve_system=False)
        user_context = "\n".join(
            f"{msg['role']}: {msg['content'][:300]}" for msg in recent
        )

        memory_summary = format_memory_prompt(recovered_memory)

        prompt = (
            f"Recent conversation:\n{user_context}\n\n"
            f"{memory_summary}\n\n"
            "Which agent should handle the user's latest request? "
            "Use 'full_pipeline' for complex multi-step analysis/onboarding tasks."
        )

        try:
            result = await self.llm.complete_json(
                system=self.SYSTEM_PROMPT,
                user=prompt,
                schema_hint={"route": "string", "reasoning": "string"},
            )
            return RouteDecision.model_validate(result)
        except Exception:
            # Fallback: if classification fails, run full pipeline to be safe
            return RouteDecision(
                route="full_pipeline",
                reasoning="Classification failed; defaulting to full pipeline.",
            )
