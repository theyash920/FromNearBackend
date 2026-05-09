import asyncio

from app.db.session import AsyncSessionLocal
from app.schemas import VendorInput
from app.workers.celery_app import celery_app
from app.workflows.growth_workflow import GrowthWorkflow


@celery_app.task(name="app.workers.tasks.run_growth_workflow", autoretry_for=(Exception,), retry_kwargs={"max_retries": 2})
def run_growth_workflow(run_id: str, payload: dict) -> dict:
    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            workflow = GrowthWorkflow()
            return await workflow.run(session, run_id, VendorInput.model_validate(payload))

    return asyncio.run(_run())
