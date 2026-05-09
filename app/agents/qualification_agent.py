from app.agents.base import AgentBase
from app.agents.state import GrowthState
from app.tools.lead_scoring import LeadScoringEngine


class QualificationAgent(AgentBase):
    name = "qualification_agent"

    def __init__(self):
        super().__init__()
        self.scoring = LeadScoringEngine()

    async def __call__(self, state: GrowthState) -> GrowthState:
        await self.emit(state, "Scoring lead quality and pain points")
        vendor = state["input"]
        deterministic_score = self.scoring.score(
            state.get("research", {}), vendor.get("category"), vendor.get("location")
        )

        # Token-efficient: only pass AI enrichment summary + base score, not raw research
        ai_enrichment = state.get("research", {}).get("ai_enrichment", {})
        compact_data = {
            "business_name": vendor.get("business_name", ""),
            "category": vendor.get("category", ""),
            "location": vendor.get("location", ""),
            "business_summary": ai_enrichment.get("business_summary", "")[:300],
            "maturity": ai_enrichment.get("business_maturity", ""),
            "base_score": deterministic_score.get("lead_score", 0),
            "base_tier": deterministic_score.get("qualification_tier", ""),
        }

        prompt = self.build_compact_prompt(
            state,
            task_description="Create pain point analysis, revenue potential, and qualification logic for this lead.",
            relevant_data=compact_data,
        )

        ai_score = await self.llm.complete_json(
            system="You are a B2B local commerce qualification expert.",
            user=prompt,
            schema_hint={
                "pain_points": ["string"],
                "revenue_potential": "string",
                "qualification_tier": "low|medium|high|strategic",
                "confidence": "number",
                "lead_score": "integer",
            },
        )
        state["qualification"] = {**deterministic_score, **ai_score}
        self.trace(state, "Computed fit, urgency, confidence, and revenue potential.")
        return state
