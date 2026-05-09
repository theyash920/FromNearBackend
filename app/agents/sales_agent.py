from app.agents.base import AgentBase
from app.agents.state import GrowthState


class SalesAgent(AgentBase):
    name = "sales_agent"

    async def __call__(self, state: GrowthState) -> GrowthState:
        await self.emit(state, "Generating personalized sales motion")

        # Token-efficient: only pass compact summaries, not full upstream state
        vendor = state.get("input", {})
        qualification = state.get("qualification", {})
        ai_enrichment = state.get("research", {}).get("ai_enrichment", {})

        compact_data = {
            "business_name": vendor.get("business_name", ""),
            "category": vendor.get("category", ""),
            "location": vendor.get("location", ""),
            "business_summary": ai_enrichment.get("business_summary", "")[:200],
            "lead_score": qualification.get("lead_score", 0),
            "qualification_tier": qualification.get("qualification_tier", ""),
            "pain_points": qualification.get("pain_points", [])[:3],
            "revenue_potential": qualification.get("revenue_potential", ""),
        }

        prompt = self.build_compact_prompt(
            state,
            task_description="Generate outreach strategy, pitch, objection handling, CTA, and follow-ups.",
            relevant_data=compact_data,
        )

        sales = await self.llm.complete_json(
            system="You are FromNear's autonomous sales employee. Personalize, be concrete, and avoid hype.",
            user=prompt,
            schema_hint={
                "outreach_strategy": "string",
                "sales_pitch": "string",
                "objection_handling": ["string"],
                "follow_ups": [
                    {"day": "integer", "channel": "instagram_dm|whatsapp|email|call", "message": "string"}
                ],
                "next_actions": ["string"],
            },
        )
        state["sales"] = sales
        self.trace(state, "Created pitch, CTA, follow-up sequence, and objection handling.")
        return state
