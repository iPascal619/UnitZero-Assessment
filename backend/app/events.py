"""Server-Sent Events manager for real-time updates (stretch item)."""

import asyncio
import json
from datetime import datetime, timezone


class EventManager:
    """Simple in-memory SSE broadcaster."""

    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        self._subscribers.remove(queue)

    async def publish(self, event_type: str, data: dict):
        """Broadcast an event to all subscribers."""
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        dead = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                dead.append(queue)
        for q in dead:
            self._subscribers.remove(q)


event_manager = EventManager()
