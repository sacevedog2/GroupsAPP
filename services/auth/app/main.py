from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as auth_router
from app.core.config import Settings, get_settings
from app.db.session import close_engine, create_schema, init_engine, ping_db
from app.grpc.server import AuthGrpcServer
from app.services.event_hub import EventHub
from app.services.event_publisher import EventPublisher
from app.services.password_hasher import PasswordHasher
from app.services.token_service import TokenService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if resolved_settings.database_url.startswith("sqlite"):
            sqlite_path = resolved_settings.database_url.split("///", maxsplit=1)[-1]
            if sqlite_path and sqlite_path != ":memory:":
                Path(sqlite_path).resolve().parent.mkdir(parents=True, exist_ok=True)

        init_engine(resolved_settings.database_url)
        await create_schema()

        event_hub = EventHub()
        event_publisher = EventPublisher(resolved_settings, event_hub)
        await event_publisher.connect()

        password_hasher = PasswordHasher(
            iterations=resolved_settings.password_pbkdf2_iterations
        )
        token_service = TokenService(
            secret_key=resolved_settings.jwt_secret_key,
            issuer=resolved_settings.jwt_issuer,
            access_token_ttl_seconds=resolved_settings.access_token_ttl_seconds,
        )

        grpc_server = AuthGrpcServer(
            host=resolved_settings.grpc_host,
            port=resolved_settings.grpc_port,
            hub=event_hub,
            token_service=token_service,
        )
        await grpc_server.start()

        app.state.settings = resolved_settings
        app.state.event_hub = event_hub
        app.state.event_publisher = event_publisher
        app.state.password_hasher = password_hasher
        app.state.token_service = token_service
        app.state.grpc_server = grpc_server

        try:
            yield
        finally:
            await grpc_server.stop()
            await event_publisher.close()
            await close_engine()

    app = FastAPI(
        title="GroupsApp Auth Service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)

    @app.get("/healthz", tags=["system"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": resolved_settings.service_name}

    @app.get("/readyz", tags=["system"])
    async def readyz() -> dict[str, str]:
        try:
            await ping_db()
            return {"status": "ready"}
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"DB not ready: {exc}") from exc

    return app


app = create_app()
