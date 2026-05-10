import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.vendor_repository import VendorRepository
from app.schemas import LeadScoreCard, RunRecord, VendorInput, WorkflowStartResponse


class AnalysisService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = VendorRepository(session)

    async def start_analysis(self, payload: VendorInput) -> WorkflowStartResponse:
        vendor = await self.repo.upsert_vendor_from_input(payload)
        run = await self.repo.create_run(vendor.id, payload.model_dump(mode="json"))
        await self.session.commit()

        # Run the workflow in the background (no Celery/Redis needed)
        asyncio.create_task(self._run_workflow_background(run.id, payload))

        return WorkflowStartResponse(
            run_id=run.id, status="queued", monitor_url=f"/api/v1/runs/{run.id}"
        )

    async def _run_workflow_background(self, run_id: str, payload: VendorInput) -> None:
        """Execute the growth workflow in a background task."""
        from app.db.session import AsyncSessionLocal
        from app.workflows.growth_workflow import GrowthWorkflow

        async with AsyncSessionLocal() as session:
            try:
                await GrowthWorkflow().run(session, run_id, payload)
            except Exception as exc:
                import traceback
                traceback.print_exc()

    async def run_inline(self, payload: VendorInput) -> dict:
        vendor = await self.repo.upsert_vendor_from_input(payload)
        run = await self.repo.create_run(vendor.id, payload.model_dump(mode="json"))
        await self.session.commit()

        from app.workflows.growth_workflow import GrowthWorkflow

        return await GrowthWorkflow().run(self.session, run.id, payload)

    async def get_run(self, run_id: str) -> RunRecord | None:
        run = await self.repo.get_run(run_id)
        if not run:
            return None
        return RunRecord(
            id=run.id,
            status=run.status,
            current_agent=run.current_agent,
            input_json=run.input_json,
            output_json=run.output_json,
            reasoning_trace=run.reasoning_trace,
            errors=run.errors,
        )

    async def list_leads(self) -> list[LeadScoreCard]:
        vendors = await self.repo.list_leads()
        cards = []
        for vendor in vendors:
            cards.append(
                LeadScoreCard(
                    vendor_id=vendor.id,
                    business_name=vendor.business_name,
                    category=vendor.category,
                    location=vendor.location,
                    lead_score=vendor.lead_score,
                    confidence=vendor.confidence,
                    tier=(vendor.metadata_json or {}).get("qualification_tier", "unscored"),
                )
            )
        return cards
