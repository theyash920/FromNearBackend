from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class VendorInput(BaseModel):
    business_name: str | None = None
    website_url: HttpUrl | None = None
    instagram_url: HttpUrl | None = None
    category: str | None = None
    business_description: str | None = None
    location: str | None = None
    product_details: str | None = None


class WorkflowStartResponse(BaseModel):
    run_id: str
    status: Literal["queued", "running"]
    monitor_url: str


class FollowUp(BaseModel):
    day: int
    channel: Literal["instagram_dm", "whatsapp", "email", "call", "linkedin", "sms"]
    message: str
    objective: str


class InstagramPost(BaseModel):
    day: int
    format: str
    theme: str
    caption: str
    creative_direction: str
    cta: str


class ReelIdea(BaseModel):
    hook: str
    script_outline: list[str]
    shot_list: list[str]
    caption: str


class MarketingCampaign(BaseModel):
    campaign_name: str
    objective: str
    audience: str
    instagram_posts: list[InstagramPost] = Field(default_factory=list)
    reels: list[ReelIdea] = Field(default_factory=list)
    hooks: list[str] = Field(default_factory=list)
    captions: list[str] = Field(default_factory=list)
    budget_notes: str | None = None


class AnalysisOutput(BaseModel):
    business_summary: str
    pain_points: list[str]
    lead_score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    qualification_tier: Literal["low", "medium", "high", "strategic"]
    revenue_potential: str
    outreach_strategy: str
    sales_pitch: str
    objection_handling: list[str]
    follow_ups: list[FollowUp]
    marketing_campaign: MarketingCampaign
    reasoning_trace: list[str] = Field(default_factory=list)
    next_actions: list[str]
    validation_notes: list[str] = Field(default_factory=list)


class AgentEvent(BaseModel):
    run_id: str
    status: str
    agent: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)


class RunRecord(BaseModel):
    id: str
    status: str
    current_agent: str | None
    input_json: dict[str, Any]
    output_json: dict[str, Any]
    reasoning_trace: list[Any]
    errors: list[Any]


class CampaignRequest(BaseModel):
    vendor: VendorInput
    goal: str = "7-day Instagram onboarding campaign"
    days: int = Field(default=7, ge=1, le=30)


class LeadScoreCard(BaseModel):
    vendor_id: str
    business_name: str | None
    category: str | None
    location: str | None
    lead_score: int | None
    confidence: float | None
    tier: str
