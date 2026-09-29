import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.app.core.logging import get_logger

logger = get_logger("event_bus")


class Event(BaseModel):
    topic: str = Field(..., description="Broad topic, e.g. chat, sys, approval, reminder")
    event_type: str = Field(..., description="Specific event action, e.g. chunk, metrics, request")
    payload: dict[str, Any] = Field(default_factory=dict, description="Structured event payload")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EventBus:
    """
    Internal high-performance, bounded pub/sub event bus.
    Routes events between domain services, collectors, and the WebSocket hub.
    """

    def __init__(self, maxsize: int = 1000) -> None:
        self.maxsize = maxsize
        self._subscribers: dict[str, set[asyncio.Queue[Event]]] = {}
        self._global_subscribers: set[asyncio.Queue[Event]] = set()
        self._lock = asyncio.Lock()

    def has_subscribers(self, topic: str | None = None) -> bool:
        """Return True if there is at least one active subscriber for the given topic or globally."""
        if self._global_subscribers:
            return True
        if topic is None:
            return bool(self._subscribers)
        if topic in self._subscribers and self._subscribers[topic]:
            return True
        for key, queues in self._subscribers.items():
            if (key.startswith(f"{topic}:") or key == topic) and queues:
                return True
        return False

    async def publish(self, topic: str, event_type: str, payload: dict[str, Any]) -> None:
        """Publish an event to all subscribers of the topic and global subscribers."""
        event = Event(topic=topic, event_type=event_type, payload=payload)

        async with self._lock:
            # Target topic queues
            topic_queues = self._subscribers.get(topic, set()).copy()
            # Compound topic:event_type queues (e.g. approval:resolved, chat:tool_call)
            compound_key = f"{topic}:{event_type}"
            compound_queues = self._subscribers.get(compound_key, set()).copy()
            # Global queues (all topics)
            global_queues = self._global_subscribers.copy()

        all_queues = topic_queues.union(compound_queues).union(global_queues)
        if not all_queues:
            return

        for q in all_queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "Event queue full, dropping oldest event for subscriber",
                    topic=topic,
                    event_type=event_type,
                )
                try:
                    # Drop oldest to preserve real-time recency
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    async def subscribe(
        self, topic: str | None = None, client_queue_size: int = 100
    ) -> AsyncGenerator[Event, None]:
        """
        Subscribe to a specific topic or all topics (if topic is None).
        Yields incoming Event objects until the consumer terminates.
        """
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=client_queue_size)

        async with self._lock:
            if topic is None:
                self._global_subscribers.add(q)
            else:
                if topic not in self._subscribers:
                    self._subscribers[topic] = set()
                self._subscribers[topic].add(q)

        try:
            while True:
                event = await q.get()
                yield event
        finally:
            async with self._lock:
                if topic is None:
                    self._global_subscribers.discard(q)
                elif topic in self._subscribers:
                    self._subscribers[topic].discard(q)
                    if not self._subscribers[topic]:
                        del self._subscribers[topic]


# Global singleton instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus(maxsize=1000)
    return _event_bus
