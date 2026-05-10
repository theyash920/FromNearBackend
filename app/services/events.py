"""In-memory event bus for real-time workflow UI updates.

Uses asyncio.Queue for local pub/sub between the workflow runner
and the WebSocket endpoint. No external dependencies required.
"""

import asyncio
import json
from collections import defaultdict

from app.schemas import AgentEvent


class WorkflowEventBus:
    """Pure in-memory event bus using asyncio.Queue.

    Each listener (WebSocket connection) gets its own Queue.
    When a workflow publishes an event, it is pushed to all queues
    subscribed to that run_id.
    """

    _QUEUES: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def publish(self, event: AgentEvent) -> None:
        event_json = event.model_dump_json()
        for queue in self._QUEUES.get(event.run_id, []):
            await queue.put(event_json)

    async def listen(self, run_id: str):
        queue: asyncio.Queue = asyncio.Queue()
        self._QUEUES[run_id].append(queue)
        try:
            while True:
                message = await queue.get()
                yield json.loads(message)
        finally:
            if queue in self._QUEUES[run_id]:
                self._QUEUES[run_id].remove(queue)
            if not self._QUEUES[run_id]:
                del self._QUEUES[run_id]
