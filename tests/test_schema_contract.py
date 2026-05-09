from app.schemas import AnalysisOutput


def test_analysis_output_contract_accepts_required_json_shape():
    payload = {
        "business_summary": "A local fashion vendor with Instagram-led demand.",
        "pain_points": ["Needs local discovery"],
        "lead_score": 84,
        "confidence": 0.88,
        "qualification_tier": "high",
        "revenue_potential": "Medium-high",
        "outreach_strategy": "Lead with local demand capture.",
        "sales_pitch": "FromNear helps nearby shoppers discover and buy from you.",
        "objection_handling": ["Position as conversion layer after Instagram."],
        "follow_ups": [
            {
                "day": 2,
                "channel": "instagram_dm",
                "message": "Can I share a local campaign idea?",
                "objective": "Move to demo.",
            }
        ],
        "marketing_campaign": {
            "campaign_name": "Local Discovery Sprint",
            "objective": "Drive nearby demand.",
            "audience": "Nearby shoppers",
            "instagram_posts": [],
            "reels": [],
            "hooks": ["Your next customer is already nearby."],
            "captions": ["Discover us on FromNear."],
        },
        "reasoning_trace": [],
        "next_actions": ["Schedule onboarding call"],
        "validation_notes": [],
    }

    assert AnalysisOutput.model_validate(payload).lead_score == 84
