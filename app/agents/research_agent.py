from app.agents.base import AgentBase
from app.agents.state import GrowthState
from app.tools.instagram_analyzer import InstagramAnalyzer
from app.tools.maps_lookup import GoogleMapsLookup
from app.tools.website_scraper import WebsiteScraper


class ResearchAgent(AgentBase):
    name = "research_agent"

    def __init__(self):
        super().__init__()
        self.scraper = WebsiteScraper()
        self.instagram = InstagramAnalyzer()
        self.maps = GoogleMapsLookup()

    async def __call__(self, state: GrowthState) -> GrowthState:
        await self.emit(state, "Researching business footprint")
        vendor = state["input"]
        website = await self.scraper.scrape(vendor.get("website_url"))
        instagram = await self.instagram.analyze(vendor.get("instagram_url"))
        maps = await self.maps.lookup(vendor.get("business_name"), vendor.get("location"))
        research = {
            "website": website,
            "instagram": instagram,
            "maps": maps,
            "provided": vendor,
        }

        # Token-efficient prompt: only pass key signals, not raw HTML/full scrape
        compact_research = {
            "website_available": website.get("available", False),
            "website_summary": website.get("summary", "")[:400],
            "instagram_handle": instagram.get("handle", ""),
            "instagram_signals": instagram.get("signals", []),
            "maps_available": maps.get("available", False),
            "business_name": vendor.get("business_name") or "",
            "category": vendor.get("category") or "",
            "location": vendor.get("location") or "",
            "description": (vendor.get("business_description") or "")[:300],
        }

        prompt = self.build_compact_prompt(
            state,
            task_description="Analyze this vendor research and infer category, maturity, and a concise business summary.",
            relevant_data=compact_research,
        )

        enriched = await self.llm.complete_json(
            system="You are a local commerce research analyst for FromNear.",
            user=prompt,
            schema_hint={
                "business_summary": "string",
                "detected_category": "string",
                "business_maturity": "string",
                "research_confidence": "number",
                "notable_signals": ["string"],
            },
        )
        state["research"] = {**research, "ai_enrichment": enriched}
        self.trace(state, "Collected web, Instagram, local lookup, and AI-enriched business summary.")
        return state
