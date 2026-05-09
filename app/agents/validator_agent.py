from app.agents.base import AgentBase
from app.agents.state import GrowthState
from app.schemas import AnalysisOutput


class ValidatorAgent(AgentBase):
    """Validates, repairs, and normalizes the merged output from all agents.

    This agent is mostly deterministic (no LLM call). It ensures:
    - All required fields exist with valid defaults
    - Follow-up channels are from the allowed set
    - Campaign structure is complete
    - Output passes Pydantic validation
    """

    name = "validator_agent"

    async def __call__(self, state: GrowthState) -> GrowthState:
        await self.emit(state, "Validating JSON quality and personalization")
        qualification = state.get("qualification", {})
        sales = state.get("sales", {})
        marketing = state.get("marketing", {})
        research = state.get("research", {}).get("ai_enrichment", {})

        follow_ups = []
        allowed_channels = {"instagram_dm", "whatsapp", "email", "call", "linkedin", "sms"}
        for item in sales.get("follow_ups", []):
            if isinstance(item, dict):
                channel = str(item.get("channel", "instagram_dm")).lower().replace(" ", "_")
                follow_ups.append(
                    {
                        "day": int(item.get("day", 2)),
                        "channel": channel if channel in allowed_channels else "instagram_dm",
                        "message": item.get("message", "Sharing a tailored FromNear onboarding idea."),
                        "objective": item.get("objective", "Move the vendor toward a short onboarding call."),
                    }
                )

        campaign = marketing.get("marketing_campaign", marketing)
        if not isinstance(campaign, dict) or not campaign.get("campaign_name"):
            campaign = {
                "campaign_name": "Local Discovery Sprint",
                "objective": "Generate local awareness and qualified inquiries.",
                "audience": "Nearby shoppers and existing social followers.",
                "instagram_posts": [],
                "reels": [],
                "hooks": ["A better way for nearby customers to discover you."],
                "captions": ["Explore this local favorite on FromNear."],
                "budget_notes": "Start with a small retargeting budget and scale winning creatives.",
            }
        campaign["objective"] = campaign.get("objective") or "Generate local awareness and qualified inquiries."
        campaign["audience"] = campaign.get("audience") or "Nearby shoppers and existing social followers."
        campaign["hooks"] = campaign.get("hooks") or ["A better way for nearby customers to discover you."]
        campaign["captions"] = campaign.get("captions") or ["Explore this local favorite on FromNear."]
        campaign["instagram_posts"] = [
            {
                "day": int(post.get("day", index + 1)),
                "format": post.get("format", "post"),
                "theme": post.get("theme", "Local discovery"),
                "caption": post.get("caption", "Discover us on FromNear."),
                "creative_direction": post.get("creative_direction", "Use authentic product and storefront visuals."),
                "cta": post.get("cta", "Message to order or visit FromNear."),
            }
            for index, post in enumerate(campaign.get("instagram_posts", []))
            if isinstance(post, dict)
        ]
        campaign["reels"] = [
            {
                "hook": reel.get("hook", "Your next local find is nearby."),
                "script_outline": reel.get("script_outline", ["Show product", "Show benefit", "End with CTA"]),
                "shot_list": reel.get("shot_list", ["Storefront", "Product close-up", "Customer moment"]),
                "caption": reel.get("caption", "Find us on FromNear."),
            }
            for reel in campaign.get("reels", [])
            if isinstance(reel, dict)
        ]

        merged = {
            "business_summary": research.get("business_summary")
            or qualification.get("business_summary")
            or "Local business profile analyzed for FromNear onboarding.",
            "pain_points": qualification.get("pain_points", []),
            "lead_score": int(qualification.get("lead_score", 70)),
            "confidence": float(qualification.get("confidence", 0.7)),
            "qualification_tier": qualification.get("qualification_tier", "high"),
            "revenue_potential": qualification.get("revenue_potential", "Medium"),
            "outreach_strategy": sales.get("outreach_strategy", ""),
            "sales_pitch": sales.get("sales_pitch", ""),
            "objection_handling": sales.get("objection_handling", []),
            "follow_ups": follow_ups,
            "marketing_campaign": campaign,
            "reasoning_trace": state.get("reasoning_trace", []),
            "next_actions": sales.get("next_actions", []),
            "validation_notes": [],
        }

        if not merged["sales_pitch"]:
            merged["validation_notes"].append("Sales pitch was regenerated from fallback strategy.")
            merged["sales_pitch"] = (
                "FromNear can turn your local visibility into measurable demand with a storefront, "
                "campaigns, and follow-ups built around nearby customers."
            )
        if not merged["pain_points"]:
            merged["pain_points"] = ["Needs clearer local discovery, conversion, and retention workflows."]
        if not merged["follow_ups"]:
            merged["follow_ups"] = [
                {
                    "day": 2,
                    "channel": "instagram_dm",
                    "message": "I drafted a local campaign idea for your FromNear launch. Can I share it?",
                    "objective": "Restart the conversation with useful personalization.",
                }
            ]

        validated = AnalysisOutput.model_validate(merged).model_dump()
        state["validated_output"] = validated
        self.trace(state, "Validated final response against structured schema.")
        return state
