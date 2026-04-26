from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as notifications_router
from app.core.config import Settings, get_settings
from app.core.observability import configure_observability
from app.db.session import close_engine, create_schema, init_engine, ping_db
from app.services.event_consumer import EventConsumer

logger = logging.getLogger(__name__)


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

        event_consumer = EventConsumer(
            settings=resolved_settings,
        )
        await event_consumer.start()

        app.state.settings = resolved_settings
        app.state.event_consumer = event_consumer
        logger.info("service.started api_port=%s", resolved_settings.api_port)

        try:
            yield
        finally:
            logger.info("service.stopping")
            await event_consumer.stop()
            await close_engine()

    app = FastAPI(
        title="GroupsApp Notifications Service",
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
    configure_observability(
        app,
        service_name=resolved_settings.service_name,
        environment=resolved_settings.environment,
        log_level=resolved_settings.log_level,
        log_dir=resolved_settings.log_dir,
        log_max_bytes=resolved_settings.log_max_bytes,
        log_backup_count=resolved_settings.log_backup_count,
    )
    app.include_router(notifications_router)

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
