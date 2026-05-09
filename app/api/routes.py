from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas import AnalysisOutput, LeadScoreCard, RunRecord, VendorInput, WorkflowStartResponse
from app.schemas.response_schemas import ChatRequest, ChatResponse
from app.services.analysis_service import AnalysisService
from app.services.controller import AgentController
from app.services.events import WorkflowEventBus

router = APIRouter(prefix="/api/v1", tags=["growth-employee"])


@router.post("/analyze", response_model=WorkflowStartResponse)
async def analyze_vendor(
    payload: VendorInput, session: AsyncSession = Depends(get_db)
) -> WorkflowStartResponse:
    return await AnalysisService(session).start_analysis(payload)


@router.post("/analyze/inline", response_model=AnalysisOutput)
async def analyze_vendor_inline(
    payload: VendorInput, session: AsyncSession = Depends(get_db)
) -> AnalysisOutput:
    output = await AnalysisService(session).run_inline(payload)
    return AnalysisOutput.model_validate(output)


@router.get("/runs/{run_id}", response_model=RunRecord)
async def get_run(run_id: str, session: AsyncSession = Depends(get_db)) -> RunRecord:
    run = await AnalysisService(session).get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/leads", response_model=list[LeadScoreCard])
async def list_leads(session: AsyncSession = Depends(get_db)) -> list[LeadScoreCard]:
    return await AnalysisService(session).list_leads()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, session: AsyncSession = Depends(get_db)) -> ChatResponse:
    """Token-efficient conversational endpoint with routing + memory.

    Pipeline:
    1. Truncates messages to sliding window (messages[-3:])
    2. Extracts recovered memory from last assistant response
    3. Routes to the correct agent via lightweight classifier
    4. Returns structured response with updated hidden-state memory

    The frontend should store the full response and pass it back on
    subsequent requests. The controller handles memory reconstruction.
    """
    controller = AgentController(session)
    return await controller.process(
        messages=[msg.model_dump() for msg in request.messages],
        vendor_context=request.vendor_context,
        session_id=request.session_id,
    )


@router.websocket("/ws/workflows/{run_id}")
async def workflow_events(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    event_bus = WorkflowEventBus()
    try:
        async for event in event_bus.listen(run_id):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return
