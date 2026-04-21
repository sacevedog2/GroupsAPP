from __future__ import annotations

import asyncio
import importlib
import json
import logging
import sys
from dataclasses import dataclass

import grpc

from app.db.models import User
from app.db.session import session_scope
from app.grpc.generator import ensure_generated
from app.services.event_hub import EventHub
from app.services.token_service import TokenService, TokenValidationError

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

    pb2 = importlib.import_module("auth_pb2")
    pb2_grpc = importlib.import_module("auth_pb2_grpc")
    return PbModules(pb2=pb2, pb2_grpc=pb2_grpc)


class AuthInternalServicer:
    def __init__(self, hub: EventHub, pb2: object, token_service: TokenService) -> None:
        self.hub = hub
        self.pb2 = pb2
        self.token_service = token_service

    async def ValidateToken(self, request, context):  # noqa: N802 (gRPC naming)
        access_token = request.access_token.strip()
        if not access_token:
            return self.pb2.TokenValidationResponse(
                valid=False,
                reason="Token vacio.",
            )

        try:
            claims, expires_at_epoch_ms = self.token_service.validate_access_token(
                access_token
            )
        except TokenValidationError as exc:
            return self.pb2.TokenValidationResponse(valid=False, reason=str(exc))

        async with session_scope() as session:
            user = await session.get(User, claims.sub)

        if user is None or not user.is_active:
            return self.pb2.TokenValidationResponse(
                valid=False,
                reason="Usuario no valido para el token.",
            )

        return self.pb2.TokenValidationResponse(
            valid=True,
            user_id=user.user_id,
            email=user.email,
            expires_at_epoch_ms=expires_at_epoch_ms,
        )

    async def GetUser(self, request, context):  # noqa: N802 (gRPC naming)
        user_id = request.user_id.strip()
        if not user_id:
            return self.pb2.UserProfile(found=False)

        async with session_scope() as session:
            user = await session.get(User, user_id)

        if user is None:
            return self.pb2.UserProfile(found=False)

        return self.pb2.UserProfile(
            found=True,
            user_id=user.user_id,
            email=user.email,
            display_name=user.display_name or "",
            is_active=user.is_active,
            created_at_epoch_ms=int(user.created_at.timestamp() * 1000),
            last_login_at_epoch_ms=(
                int(user.last_login_at.timestamp() * 1000) if user.last_login_at else 0
            ),
        )

    async def StreamEvents(self, request, context):  # noqa: N802 (gRPC naming)
        queue = self.hub.subscribe()
        filters = set(request.event_types)

        try:
            while True:
                event = await queue.get()
                if filters and event.event_type not in filters:
                    continue

                yield self.pb2.AuthEvent(
                    id=event.id,
                    event_type=event.event_type,
                    subject_type=event.subject_type,
                    subject_id=event.subject_id,
                    payload_json=json.dumps(event.payload, ensure_ascii=False),
                    created_at_epoch_ms=int(event.created_at.timestamp() * 1000),
                )
        except asyncio.CancelledError:
            raise
        finally:
            self.hub.unsubscribe(queue)


class AuthGrpcServer:
    def __init__(
        self,
        host: str,
        port: int,
        hub: EventHub,
        token_service: TokenService,
    ) -> None:
        self.host = host
        self.port = port
        self.hub = hub
        self.token_service = token_service
        self._server: grpc.aio.Server | None = None

    async def start(self) -> None:
        if self._server is not None:
            return

        modules = load_pb_modules()
        self._server = grpc.aio.server()
        servicer = AuthInternalServicer(
            hub=self.hub,
            pb2=modules.pb2,
            token_service=self.token_service,
        )
        modules.pb2_grpc.add_AuthInternalServicer_to_server(servicer, self._server)
        address = f"{self.host}:{self.port}"
        self._server.add_insecure_port(address)
        await self._server.start()
        logger.info("gRPC server activo en %s", address)

    async def stop(self) -> None:
        if self._server is None:
            return
        await self._server.stop(grace=2)
        self._server = None
