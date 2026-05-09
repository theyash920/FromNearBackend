from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRun, Campaign, MemoryItem, OutreachAttempt, Vendor
from app.schemas import VendorInput


class VendorRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_vendor(self, payload: VendorInput) -> Vendor:
        vendor = Vendor(
            business_name=payload.business_name,
            website_url=str(payload.website_url) if payload.website_url else None,
            instagram_url=str(payload.instagram_url) if payload.instagram_url else None,
            category=payload.category,
            location=payload.location,
            product_details=payload.product_details,
            description=payload.business_description,
            metadata_json={},
        )
        self.session.add(vendor)
        await self.session.flush()
        return vendor

    async def upsert_vendor_from_input(self, payload: VendorInput) -> Vendor:
        lookup = []
        if payload.website_url:
            lookup.append(Vendor.website_url == str(payload.website_url))
        if payload.instagram_url:
            lookup.append(Vendor.instagram_url == str(payload.instagram_url))
        if lookup:
            result = await self.session.execute(select(Vendor).where(or_(*lookup)).limit(1))
            existing = result.scalar_one_or_none()
            if existing:
                existing.business_name = payload.business_name or existing.business_name
                existing.category = payload.category or existing.category
                existing.location = payload.location or existing.location
                existing.product_details = payload.product_details or existing.product_details
                existing.description = payload.business_description or existing.description
                await self.session.flush()
                return existing
        return await self.create_vendor(payload)

    async def update_vendor_score(
        self, vendor_id: str, lead_score: int, confidence: float, maturity: str | None, metadata: dict
    ) -> None:
        vendor = await self.session.get(Vendor, vendor_id)
        if vendor:
            vendor.lead_score = lead_score
            vendor.confidence = confidence
            vendor.maturity = maturity
            vendor.metadata_json = {**(vendor.metadata_json or {}), **metadata}
            await self.session.flush()

    async def create_run(self, vendor_id: str | None, input_json: dict) -> AgentRun:
        run = AgentRun(vendor_id=vendor_id, input_json=input_json, status="queued")
        self.session.add(run)
        await self.session.flush()
        return run

    async def update_run(
        self,
        run_id: str,
        status: str,
        current_agent: str | None = None,
        output_json: dict | None = None,
        reasoning_trace: list | None = None,
        errors: list | None = None,
    ) -> AgentRun | None:
        run = await self.session.get(AgentRun, run_id)
        if not run:
            return None
        run.status = status
        run.current_agent = current_agent or run.current_agent
        if output_json is not None:
            run.output_json = output_json
        if reasoning_trace is not None:
            run.reasoning_trace = reasoning_trace
        if errors is not None:
            run.errors = errors
        await self.session.flush()
        return run

    async def get_run(self, run_id: str) -> AgentRun | None:
        return await self.session.get(AgentRun, run_id)

    async def list_runs(self, limit: int = 25) -> list[AgentRun]:
        result = await self.session.execute(
            select(AgentRun).order_by(desc(AgentRun.created_at)).limit(limit)
        )
        return list(result.scalars().all())

    async def list_leads(self, limit: int = 50) -> list[Vendor]:
        result = await self.session.execute(
            select(Vendor).order_by(desc(Vendor.lead_score), desc(Vendor.created_at)).limit(limit)
        )
        return list(result.scalars().all())

    async def add_campaign(self, vendor_id: str, name: str, payload: dict) -> Campaign:
        campaign = Campaign(vendor_id=vendor_id, name=name, campaign_json=payload)
        self.session.add(campaign)
        await self.session.flush()
        return campaign

    async def add_outreach_attempt(
        self, vendor_id: str, channel: str, message: str, metadata: dict | None = None
    ) -> OutreachAttempt:
        attempt = OutreachAttempt(
            vendor_id=vendor_id, channel=channel, message=message, metadata_json=metadata or {}
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def add_memory(
        self, vendor_id: str | None, kind: str, content: str, memory_json: dict | None = None
    ) -> MemoryItem:
        item = MemoryItem(
            vendor_id=vendor_id, kind=kind, content=content, memory_json=memory_json or {}
        )
        self.session.add(item)
        await self.session.flush()
        return item
