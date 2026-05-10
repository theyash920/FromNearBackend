import json
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings


class LocalLLMClient:
    """Thin Ollama client that keeps the app local-first and JSON-oriented."""

    def __init__(self) -> None:
        self.settings = get_settings()

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def complete_json(
        self,
        system: str,
        user: str,
        schema_hint: dict[str, Any],
        model: str | None = None,
    ) -> dict[str, Any]:
        prompt = (
            f"{system}\n\n"
            "Return ONLY valid JSON. Do not wrap the JSON in markdown.\n"
            f"Expected schema keys: {json.dumps(schema_hint)}\n\n"
        )
        
        if self.settings.groq_api_key:
            selected_model = model or "llama3-8b-8192"
            try:
                async with httpx.AsyncClient(timeout=90) as client:
                    response = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {self.settings.groq_api_key}"},
                        json={
                            "model": selected_model,
                            "messages": [
                                {"role": "system", "content": prompt},
                                {"role": "user", "content": user}
                            ],
                            "response_format": {"type": "json_object"},
                            "temperature": 0.25,
                        },
                    )
                    response.raise_for_status()
                raw = response.json()["choices"][0]["message"].get("content", "{}")
                return json.loads(raw)
            except Exception:
                return self._deterministic_fallback(user)

        # Fallback to Ollama
        selected_model = model or self.settings.ollama_chat_model
        prompt_with_user = f"{prompt}Task:\n{user}"
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                response = await client.post(
                    f"{self.settings.ollama_base_url}/api/generate",
                    json={
                        "model": selected_model,
                        "prompt": prompt_with_user,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0.25},
                    },
                )
                response.raise_for_status()
            raw = response.json().get("response", "{}")
            return json.loads(raw)
        except Exception:
            return self._deterministic_fallback(user)

    async def embed(self, text: str) -> list[float]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.settings.ollama_base_url}/api/embeddings",
                    json={"model": self.settings.ollama_embed_model, "prompt": text},
                )
                response.raise_for_status()
            return response.json().get("embedding", [])
        except Exception:
            return []

    def _deterministic_fallback(self, user: str) -> dict[str, Any]:
        """Useful for demos when Ollama is not warm yet; no paid API dependency."""
        lowered = user.lower()
        category = "local business"
        for candidate in ["restaurant", "fashion", "electronics", "service", "salon", "cafe"]:
            if candidate in lowered:
                category = candidate
                break
        return {
            "business_summary": f"A {category} lead with visible local-market potential.",
            "pain_points": [
                "Discovery depends on word of mouth and fragmented social channels.",
                "Online catalog and ordering flows appear under-optimized.",
                "Follow-up and retention campaigns can be more systematic.",
            ],
            "lead_score": 78,
            "confidence": 0.72,
            "qualification_tier": "high",
            "revenue_potential": "Medium-high based on category fit and local acquisition needs.",
            "outreach_strategy": "Lead with FromNear's local demand capture and low-friction onboarding.",
            "sales_pitch": (
                "FromNear can help you convert nearby intent into orders by showcasing your catalog, "
                "running location-aware campaigns, and automating follow-ups from one workflow."
            ),
            "objection_handling": [
                "If they already use Instagram, position FromNear as the conversion layer after discovery.",
                "If they worry about time, offer done-for-you onboarding and campaign drafts.",
            ],
            "follow_ups": [
                {
                    "day": 2,
                    "channel": "instagram_dm",
                    "message": "Sharing a quick local campaign idea tailored to your audience.",
                    "objective": "Re-open conversation with value.",
                },
                {
                    "day": 5,
                    "channel": "whatsapp",
                    "message": "Can we set up a 15-minute onboarding walkthrough this week?",
                    "objective": "Move to demo.",
                },
            ],
            "marketing_campaign": {
                "campaign_name": "Local Discovery Sprint",
                "objective": "Increase profile visits, inquiries, and first orders in 7 days.",
                "audience": "Nearby shoppers and repeat local customers.",
                "instagram_posts": [],
                "reels": [],
                "hooks": [
                    "Your next favorite local find is closer than you think.",
                    "New arrivals, local prices, instant discovery.",
                ],
                "captions": ["Discover local picks on FromNear today."],
                "budget_notes": "Start small, retarget engagers, then scale winning creatives.",
            },
            "next_actions": [
                "Verify catalog depth and delivery/service radius.",
                "Send personalized pitch with one sample campaign.",
                "Schedule onboarding call.",
            ],
        }
