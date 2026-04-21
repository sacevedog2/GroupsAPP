from __future__ import annotations

import logging

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message as MQMessage

from app.core.config import Settings
from app.schemas.events import DomainEvent
from app.services.event_hub import EventHub

logger = logging.getLogger(__name__)


class EventPublisher:
    def __init__(self, settings: Settings, hub: EventHub) -> None:
        self.settings = settings
        self.hub = hub
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def connect(self) -> None:
        if not self.settings.rabbitmq_url:
            logger.info("RabbitMQ no configurado: modo solo stream gRPC interno.")
            return

        try:
            self._connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
            self._channel = await self._connection.channel(publisher_confirms=False)
            self._exchange = await self._channel.declare_exchange(
                self.settings.rabbitmq_exchange,
                ExchangeType.TOPIC,
                durable=True,
            )
            logger.info(
                "Conectado a RabbitMQ exchange=%s", self.settings.rabbitmq_exchange
            )
        except Exception:
            logger.exception(
                "No fue posible conectar RabbitMQ. Se continua sin MOM externo."
            )
            self._connection = None
            self._channel = None
            self._exchange = None

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
        self._connection = None
        self._channel = None
        self._exchange = None

    async def publish(self, event: DomainEvent) -> None:
        await self.hub.publish(event)

        if self._exchange is None:
            return

        routing_key = f"auth.{event.event_type}"
        body = event.model_dump_json().encode("utf-8")
        mq_message = MQMessage(
            body=body,
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
            timestamp=event.created_at,
        )
        try:
            await self._exchange.publish(mq_message, routing_key=routing_key)
        except Exception:
            logger.exception("Fallo al publicar evento en RabbitMQ: %s", routing_key)
