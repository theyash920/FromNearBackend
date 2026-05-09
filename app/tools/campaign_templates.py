class CampaignTemplateRetriever:
    def get_templates(self, category: str | None) -> list[dict]:
        category_key = (category or "local").lower()
        base = {
            "restaurant": [
                "7-day launch: chef story, best-seller reel, lunch offer, UGC repost, local collab"
            ],
            "fashion": [
                "Drop campaign: arrival teaser, styling reel, price anchor, creator try-on, weekend CTA"
            ],
            "electronics": [
                "Trust campaign: product demo, warranty proof, comparison carousel, service CTA"
            ],
        }
        return [{"category": category_key, "template": t} for t in base.get(category_key, base["restaurant"])]
