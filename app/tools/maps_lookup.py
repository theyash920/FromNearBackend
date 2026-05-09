class GoogleMapsLookup:
    async def lookup(self, business_name: str | None, location: str | None) -> dict:
        return {
            "available": bool(business_name or location),
            "summary": (
                "Maps lookup is implemented as a provider interface. Add Google Places, SerpAPI, "
                "or a local business registry key without changing agent code."
            ),
            "query": {"business_name": business_name, "location": location},
            "signals": ["Local intent exists", "Location-based campaigns can be generated"],
        }
