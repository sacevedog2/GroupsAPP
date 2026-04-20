from __future__ import annotations

import asyncio
import importlib
import json
import logging
import sys
from dataclasses import dataclass

import grpc

from app.grpc.generator import ensure_generated
from app.services.event_hub import EventHub

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PbModules:
    pb2: object
    pb2_grpc: object


def load_pb_modules() -> PbModules:
    generated_dir = ensure_generated()
    generated_path = str(generated_dir)
    if generated_path not in sys.path:
        sys.path.insert(0, generated_path)

    pb2 = importlib.import_module("messaging_pb2")
    pb2_grpc = importlib.import_module("messaging_pb2_grpc")
    return PbModules(pb2=pb2, pb2_grpc=pb2_grpc)


class MessagingInternalServicer:
    def __init__(self, hub: EventHub, pb2: object) -> None:
        self.hub = hub
        self.pb2 = pb2

    async def StreamEvents(self, request, context):  # noqa: N802 (gRPC naming)
        queue = self.hub.subscribe()
        filters = set(request.event_types)

        try:
            while True:
                event = await queue.get()
                if filters and event.event_type not in filters:
                    continue

                yield self.pb2.MessagingEvent(
                    id=event.id,
                    event_type=event.event_type,
                    scope_type=event.scope_type.value,
                    scope_id=event.scope_id,
                    payload_json=json.dumps(event.payload, ensure_ascii=False),
                    created_at_epoch_ms=int(event.created_at.timestamp() * 1000),
                )
        except asyncio.CancelledError:
            raise
        finally:
            self.hub.unsubscribe(queue)


class MessagingGrpcServer:
    def __init__(self, host: str, port: int, hub: EventHub) -> None:
        self.host = host
        self.port = port
        self.hub = hub
        self._server: grpc.aio.Server | None = None

    async def start(self) -> None:
        if self._server is not None:
            return

        modules = load_pb_modules()
        self._server = grpc.aio.server()
        servicer = MessagingInternalServicer(hub=self.hub, pb2=modules.pb2)
        modules.pb2_grpc.add_MessagingInternalServicer_to_server(
            servicer, self._server
        )
        address = f"{self.host}:{self.port}"
        self._server.add_insecure_port(address)
        await self._server.start()
        logger.info("gRPC server activo en %s", address)

    async def stop(self) -> None:
        if self._server is None:
            return
        await self._server.stop(grace=2)
        self._server = None
