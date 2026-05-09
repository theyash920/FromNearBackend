class InstagramAnalyzer:
    async def analyze(self, url: str | None) -> dict:
        if not url:
            return {"available": False, "summary": "No Instagram page supplied."}
        handle = url.rstrip("/").split("/")[-1]
        return {
            "available": True,
            "handle": handle,
            "summary": (
                f"Instagram profile @{handle} should be reviewed for posting cadence, "
                "catalog clarity, offer quality, UGC, reels usage, and CTA strength."
            ),
            "signals": [
                "Visual-first channel available for personalized outreach.",
                "Potential to convert followers into FromNear catalog traffic.",
            ],
        }
