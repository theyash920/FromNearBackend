"""Main orchestration controller for the token-efficient agent pipeline.

Pipeline flow:
    User Message
        ↓
    Context Truncation (messages[-3:])
        ↓
    Memory Extraction (scan backward for last memory JSON)
        ↓
    Classifier Agent (lightweight routing)
        ↓
    Selected Worker Agent  OR  Full Pipeline
        ↓
    Structured JSON Response { "response": ..., "memory": ... }
        ↓
    Persist Updated Memory (MySQL persistent)
        ↓
    Return Response
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.router_agent import RouterAgent
from app.agents.state import GrowthState
from app.core.logging import logger
from app.repositories.vendor_repository import VendorRepository
from app.schemas import VendorInput
from app.schemas.response_schemas import AgentMemory, AgentResponse, ChatResponse
from app.services.context_window import truncate_messages
from app.services.memory_manager import (
    SessionMemoryStore,
    extract_memory,
    format_memory_prompt,
    merge_memory,
)


class AgentController:
    """Orchestrates the token-efficient agent pipeline.

    This controller ensures:
    1. NEVER sends full conversation history to any LLM call
    2. Always uses sliding window truncation (messages[-3:])
    3. Reconstructs context from the latest stored memory object
    4. Routes to single agent OR full pipeline based on classifier
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = VendorRepository(session)
        self.router = RouterAgent()
        self.session_store = SessionMemoryStore()

    async def process(
        self,
        messages: list[dict[str, Any]],
        vendor_context: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> ChatResponse:
        """Process a user message through the token-efficient pipeline."""
        session_id = session_id or str(uuid4())

        # Step 1: Extract memory from message history
        recovered_memory = extract_memory(messages)

        # Step 2: Try to recover from session store if no memory in messages
        if recovered_memory is None:
            redis_session = await self.session_store.load_session(session_id)
            if redis_session and "memory_snapshot" in redis_session:
                try:
                    recovered_memory = AgentMemory.model_validate(redis_session["memory_snapshot"])
                except Exception:
                    pass

        # Step 3: Truncate context (NEVER send full history)
        truncated = truncate_messages(messages, window_size=3)

        # Step 4: Route using lightweight classifier
        route_decision = await self.router.classify(truncated, recovered_memory)
        logger.info("agent_routed", route=route_decision.route, reasoning=route_decision.reasoning)

        # Step 5: Update session store with active agent
        await self.session_store.update_active_agent(session_id, route_decision.route)

        # Step 6: Execute the selected agent(s)
        if route_decision.route == "full_pipeline":
            agent_output = await self._run_full_pipeline(truncated, recovered_memory, vendor_context)
        else:
            agent_output = await self._run_single_agent(
                route_decision.route, truncated, recovered_memory, vendor_context
            )

        # Step 7: Merge and persist memory
        updated_memory = merge_memory(recovered_memory, {
            "active_agent": route_decision.route,
            "completed_stage": route_decision.route,
            "accumulated_data": agent_output.response,
        })

        # Step 8: Cache in session store
        await self.session_store.cache_recent_context(
            session_id,
            messages,
            updated_memory.model_dump(),
        )

        # Step 9: Persist to MySQL (long-term)
        await self._persist_conversation(session_id, messages, updated_memory, vendor_context)

        return ChatResponse(
            response=agent_output.response,
            memory=updated_memory,
            routed_to=route_decision.route,
            session_id=session_id,
        )

    async def _run_single_agent(
        self,
        agent_name: str,
        messages: list[dict[str, Any]],
        memory: AgentMemory | None,
        vendor_context: dict[str, Any] | None,
    ) -> AgentResponse:
        """Run a single worker agent with token-efficient prompting."""
        from app.agents import (
            MarketingAgent,
            QualificationAgent,
            ResearchAgent,
            SalesAgent,
            ValidatorAgent,
        )

        agent_map = {
            "research_agent": ResearchAgent,
            "qualification_agent": QualificationAgent,
            "sales_agent": SalesAgent,
            "marketing_agent": MarketingAgent,
            "validator_agent": ValidatorAgent,
        }

        agent_cls = agent_map.get(agent_name)
        if agent_cls is None:
            return AgentResponse(
                response={"error": f"Unknown agent: {agent_name}"},
                memory=memory or AgentMemory(),
            )

        agent = agent_cls()

        # Build a minimal GrowthState from memory + vendor context
        state: GrowthState = {
            "run_id": "",
            "vendor_id": None,
            "input": vendor_context or memory.vendor_context if memory else {},
            "reasoning_trace": [],
            "errors": [],
            "retry_count": 0,
        }

        # Inject accumulated data from memory into the appropriate state key
        if memory and memory.accumulated_data:
            for key in ("research", "qualification", "sales", "marketing"):
                if key in memory.accumulated_data:
                    state[key] = memory.accumulated_data[key]

        # Set the recovered memory in the agent's system prompt via the state
        state["_recovered_memory"] = format_memory_prompt(memory)
        state["_recent_messages"] = messages

        result_state = await agent(state)

        # Extract the agent's output from state
        output_key = agent_name.replace("_agent", "")
        agent_output = result_state.get(output_key, result_state.get("validated_output", {}))

        return AgentResponse(
            response=agent_output if isinstance(agent_output, dict) else {"result": str(agent_output)},
            memory=memory or AgentMemory(),
        )

    async def _run_full_pipeline(
        self,
        messages: list[dict[str, Any]],
        memory: AgentMemory | None,
        vendor_context: dict[str, Any] | None,
    ) -> AgentResponse:
        """Run the full sequential pipeline: Research → Qualification → Sales → Marketing → Validator.

        Each agent receives only the compact state from the previous agent,
        never the full conversation history.
        """
        from app.workflows.growth_workflow import GrowthWorkflow

        vendor_data = vendor_context or {}
        if memory and memory.vendor_context:
            vendor_data = {**memory.vendor_context, **vendor_data}

        # Create a vendor input from available data
        payload = VendorInput(
            business_name=vendor_data.get("business_name"),
            website_url=vendor_data.get("website_url"),
            instagram_url=vendor_data.get("instagram_url"),
            category=vendor_data.get("category"),
            business_description=vendor_data.get("business_description"),
            location=vendor_data.get("location"),
            product_details=vendor_data.get("product_details"),
        )

        vendor = await self.repo.upsert_vendor_from_input(payload)
        run = await self.repo.create_run(vendor.id, payload.model_dump(mode="json"))
        await self.session.commit()

        workflow = GrowthWorkflow()
        output = await workflow.run(self.session, run.id, payload)

        return AgentResponse(
            response=output,
            memory=memory or AgentMemory(),
        )

    async def _persist_conversation(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
        memory: AgentMemory,
        vendor_context: dict[str, Any] | None,
    ) -> None:
        """Persist conversation state to MySQL for long-term storage."""
        from app.models import Conversation
        from sqlalchemy import select

        try:
            result = await self.session.execute(
                select(Conversation).where(Conversation.session_id == session_id).limit(1)
            )
            conversation = result.scalar_one_or_none()

            if conversation:
                conversation.messages_json = messages
                conversation.memory_snapshot = memory.model_dump()
            else:
                vendor_id = None
                if vendor_context and vendor_context.get("vendor_id"):
                    vendor_id = vendor_context["vendor_id"]

                conversation = Conversation(
                    session_id=session_id,
                    vendor_id=vendor_id,
                    messages_json=messages,
                    memory_snapshot=memory.model_dump(),
                )
                self.session.add(conversation)

            await self.session.flush()
            await self.session.commit()
        except Exception as exc:
            logger.warning("conversation_persist_failed", error=str(exc))
