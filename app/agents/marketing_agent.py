from app.agents.base import AgentBase
from app.agents.state import GrowthState
from app.tools.campaign_templates import CampaignTemplateRetriever


class MarketingAgent(AgentBase):
    name = "marketing_agent"

    def __init__(self):
        super().__init__()
        self.templates = CampaignTemplateRetriever()

    async def __call__(self, state: GrowthState) -> GrowthState:
        await self.emit(state, "Building campaign concepts and creatives")
        vendor = state.get("input", {})
        templates = self.templates.get_templates(vendor.get("category"))

        # Token-efficient: only pass category + qualification summary + sales strategy hint
        qualification = state.get("qualification", {})
        sales = state.get("sales", {})
        ai_enrichment = state.get("research", {}).get("ai_enrichment", {})

        compact_data = {
            "business_name": vendor.get("business_name", ""),
            "category": vendor.get("category", ""),
            "location": vendor.get("location", ""),
            "business_summary": ai_enrichment.get("business_summary", "")[:200],
            "qualification_tier": qualification.get("qualification_tier", ""),
            "outreach_strategy": sales.get("outreach_strategy", "")[:200],
            "templates": str(templates)[:300],
        }

        prompt = self.build_compact_prompt(
            state,
            task_description=(
                "Create a structured 7-day Instagram and launch campaign with hooks, reels, captions, "
                "creative direction, and budget notes."
            ),
            relevant_data=compact_data,
        )

        marketing = await self.llm.complete_json(
            system="You are a growth marketer for Indian local businesses joining FromNear.",
            user=prompt,
            schema_hint={
                "marketing_campaign": {
                    "campaign_name": "string",
                    "objective": "string",
                    "audience": "string",
                    "instagram_posts": [
                        {
                            "day": "integer",
                            "format": "string",
                            "theme": "string",
                            "caption": "string",
                            "creative_direction": "string",
                            "cta": "string",
                        }
                    ],
                    "reels": [
                        {
                            "hook": "string",
                            "script_outline": ["string"],
                            "shot_list": ["string"],
                            "caption": "string",
                        }
                    ],
                    "hooks": ["string"],
                    "captions": ["string"],
                    "budget_notes": "string",
                }
            },
        )
        state["marketing"] = marketing
        self.trace(state, "Generated campaign ideas, reel hooks, captions, and growth suggestions.")
        return state
