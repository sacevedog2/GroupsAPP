from __future__ import annotations

import asyncio

from app.schemas.events import DomainEvent


class EventHub:
    """In-memory fanout hub used by gRPC streaming consumers."""

    def __init__(self, max_queue_size: int = 1000) -> None:
        self.max_queue_size = max_queue_size
        self._subscribers: set[asyncio.Queue[DomainEvent]] = set()

    def subscribe(self) -> asyncio.Queue[DomainEvent]:
        queue: asyncio.Queue[DomainEvent] = asyncio.Queue(maxsize=self.max_queue_size)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[DomainEvent]) -> None:
        self._subscribers.discard(queue)

    async def publish(self, event: DomainEvent) -> None:
        stale_queues: list[asyncio.Queue[DomainEvent]] = []
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    stale_queues.append(queue)
                    continue

                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    stale_queues.append(queue)

        for queue in stale_queues:
            self.unsubscribe(queue)
