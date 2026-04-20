from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.api.routes import router as messaging_router
from app.core.config import Settings, get_settings
from app.db.session import close_engine, create_schema, init_engine, ping_db
from app.grpc.server import MessagingGrpcServer
from app.services.event_hub import EventHub
from app.services.event_publisher import EventPublisher
from app.services.storage import StorageService

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

        storage_service = StorageService(
            root_path=resolved_settings.attachment_root,
            max_upload_mb=resolved_settings.max_upload_mb,
        )

        grpc_server = MessagingGrpcServer(
            host=resolved_settings.grpc_host,
            port=resolved_settings.grpc_port,
            hub=event_hub,
        )
        await grpc_server.start()

        app.state.settings = resolved_settings
        app.state.event_hub = event_hub
        app.state.event_publisher = event_publisher
        app.state.storage_service = storage_service
        app.state.grpc_server = grpc_server

        try:
            yield
        finally:
            await grpc_server.stop()
            await event_publisher.close()
            await close_engine()

    app = FastAPI(
        title="GroupsApp Messaging Service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(messaging_router)

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
