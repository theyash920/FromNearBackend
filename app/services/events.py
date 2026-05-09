import json

import redis.asyncio as redis

from app.core.config import get_settings
from app.schemas import AgentEvent


class WorkflowEventBus:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def publish(self, event: AgentEvent) -> None:
        client = redis.from_url(self.settings.redis_url, decode_responses=True)
        try:
            await client.publish(f"workflow:{event.run_id}", event.model_dump_json())
        except Exception:
            # Workflow execution must not fail just because live UI streaming is unavailable.
            return
        finally:
            await client.aclose()

    async def listen(self, run_id: str):
        client = redis.from_url(self.settings.redis_url, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe(f"workflow:{run_id}")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(f"workflow:{run_id}")
            await pubsub.aclose()
            await client.aclose()
