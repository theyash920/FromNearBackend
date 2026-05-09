class LeadScoringEngine:
    def score(self, research: dict, category: str | None, location: str | None) -> dict:
        score = 45
        reasons = []
        if research.get("website", {}).get("available"):
            score += 12
            reasons.append("Website exists and can support catalog/onboarding review.")
        if research.get("instagram", {}).get("available"):
            score += 18
            reasons.append("Instagram presence enables warm personalized outreach.")
        if category:
            score += 10
            reasons.append("Category supplied; use-case can be mapped to FromNear campaigns.")
        if location:
            score += 10
            reasons.append("Location supplied; local-first positioning is clear.")
        score = min(score, 100)
        tier = "strategic" if score >= 88 else "high" if score >= 70 else "medium" if score >= 50 else "low"
        return {
            "lead_score": score,
            "qualification_tier": tier,
            "confidence": round(min(0.55 + score / 200, 0.96), 2),
            "reasons": reasons,
        }
