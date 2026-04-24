from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

import aio_pika
from aio_pika import ExchangeType, IncomingMessage

from app.core.config import Settings
from app.db.session import session_scope
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class EventConsumer:
    def __init__(
        self,
        settings: Settings,
    ) -> None:
        self.settings = settings
        self._connection: aio_pika.RobustConnection | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if not self.settings.rabbitmq_url:
            logger.info("RabbitMQ no configurado para notifications.")
            return
        self._task = asyncio.create_task(self._consume(), name="notifications-consumer")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def _consume(self) -> None:
        retry_count = 0
        while True:
            try:
                self._connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
                retry_count = 0
                channel = await self._connection.channel()
                exchange = await channel.declare_exchange(
                    self.settings.rabbitmq_exchange,
                    ExchangeType.TOPIC,
                    durable=True,
                )
                queue = await channel.declare_queue("notifications.events", durable=True)
                await queue.bind(exchange, routing_key="messaging.message.created")
                await queue.bind(exchange, routing_key="messaging.direct_conversation.started")
                await queue.bind(exchange, routing_key="member.added")

                logger.info("Notifications consumer conectado a RabbitMQ.")
                async with queue.iterator() as iterator:
                    async for message in iterator:
                        await self._handle_message(message)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                retry_count += 1
                if retry_count <= 5:
                    logger.warning(
                        "RabbitMQ aun no esta listo para notifications; reintentando en 3s. Detalle: %s",
                        exc,
                    )
                else:
                    logger.exception("Consumer de notifications fallo; reintentando.")
                await asyncio.sleep(3)

    async def _handle_message(self, message: IncomingMessage) -> None:
        async with message.process(requeue=False):
            event = self._decode_event(message)
            routing_key = message.routing_key
            async with session_scope() as session:
                service = NotificationService(
                    session=session,
                )
                if routing_key == "messaging.message.created":
                    await service.notify_unread_message(event)
                elif routing_key == "messaging.direct_conversation.started":
                    await service.notify_direct_started(event)
                elif routing_key == "member.added":
                    await service.notify_group_member_added(event)

    def _decode_event(self, message: IncomingMessage) -> dict:
        body = json.loads(message.body.decode("utf-8"))
        if "event_type" not in body:
            raw_event_id = (
                f"{message.routing_key}:"
                f"{body.get('group_id', '')}:"
                f"{body.get('user_id', '')}:"
                f"{body.get('actor_user_id', '')}"
            )
            body = {
                "id": raw_event_id if message.routing_key == "member.added" else str(uuid4()),
                "event_type": message.routing_key,
                "scope_type": "group" if message.routing_key == "member.added" else None,
                "scope_id": body.get("group_id"),
                "payload": body,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        return body
