from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import MarketingAgent, QualificationAgent, ResearchAgent, SalesAgent, ValidatorAgent
from app.agents.state import GrowthState
from app.repositories.vendor_repository import VendorRepository
from app.schemas import AgentEvent, VendorInput
from app.services.events import WorkflowEventBus
from app.services.memory import SemanticMemoryService


class GrowthWorkflow:
    def __init__(self) -> None:
        self.event_bus = WorkflowEventBus()
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(GrowthState)
        builder.add_node("research", ResearchAgent())
        builder.add_node("qualification", QualificationAgent())
        builder.add_node("sales", SalesAgent())
        builder.add_node("marketing", MarketingAgent())
        builder.add_node("validator", ValidatorAgent())

        builder.add_edge(START, "research")
        builder.add_edge("research", "qualification")
        builder.add_edge("qualification", "sales")
        builder.add_edge("sales", "marketing")
        builder.add_edge("marketing", "validator")
        builder.add_edge("validator", END)
        return builder.compile()

    async def run(self, session: AsyncSession, run_id: str, payload: VendorInput) -> dict:
        repo = VendorRepository(session)
        run = await repo.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        await repo.update_run(run_id, status="running", current_agent="research_agent")
        await session.commit()

        initial_state: GrowthState = {
            "run_id": run_id,
            "vendor_id": run.vendor_id,
            "input": payload.model_dump(mode="json"),
            "reasoning_trace": [],
            "errors": [],
            "retry_count": 0,
        }

        try:
            final_state = await self.graph.ainvoke(initial_state)
            output = final_state["validated_output"]
            output["reasoning_trace"] = final_state.get("reasoning_trace", [])

            if run.vendor_id:
                await repo.update_vendor_score(
                    vendor_id=run.vendor_id,
                    lead_score=output["lead_score"],
                    confidence=output["confidence"],
                    maturity=final_state.get("research", {})
                    .get("ai_enrichment", {})
                    .get("business_maturity"),
                    metadata={"qualification_tier": output["qualification_tier"]},
                )
                await repo.add_campaign(
                    vendor_id=run.vendor_id,
                    name=output["marketing_campaign"]["campaign_name"],
                    payload=output["marketing_campaign"],
                )
                await repo.add_outreach_attempt(
                    vendor_id=run.vendor_id,
                    channel="instagram_dm",
                    message=output["sales_pitch"],
                    metadata={"source": "sales_agent", "status": "draft"},
                )
                memory = SemanticMemoryService(session)
                await memory.remember(
                    vendor_id=run.vendor_id,
                    kind="analysis",
                    content=output["business_summary"],
                    payload=output,
                )

            await repo.update_run(
                run_id,
                status="completed",
                current_agent="completed",
                output_json=output,
                reasoning_trace=output["reasoning_trace"],
            )
            await session.commit()
            await self.event_bus.publish(
                AgentEvent(
                    run_id=run_id,
                    status="completed",
                    agent="workflow",
                    message="Workflow completed",
                    payload=output,
                )
            )
            return output
        except Exception as exc:
            await session.rollback()
            await repo.update_run(run_id, status="failed", current_agent="workflow", errors=[str(exc)])
            await session.commit()
            await self.event_bus.publish(
                AgentEvent(
                    run_id=run_id,
                    status="failed",
                    agent="workflow",
                    message=str(exc),
                    payload={},
                )
            )
            raise
