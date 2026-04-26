from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from collections import Counter
from contextvars import ContextVar
from datetime import UTC, datetime
from threading import Lock
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class RequestContextFilter(logging.Filter):
    def __init__(self, service_name: str, environment: str) -> None:
        super().__init__()
        self.service_name = service_name
        self.environment = environment

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        record.service_name = self.service_name
        record.environment = self.environment
        return True


class MetricsRegistry:
    def __init__(self, service_name: str, environment: str) -> None:
        self.service_name = service_name
        self.environment = environment
        self.started_at = datetime.now(UTC)
        self._lock = Lock()
        self._requests_total = 0
        self._requests_in_flight = 0
        self._errors_total = 0
        self._total_duration_seconds = 0.0
        self._max_duration_seconds = 0.0
        self._last_request_at: datetime | None = None
        self._requests_by_method: Counter[str] = Counter()
        self._responses_by_status: Counter[str] = Counter()

    def mark_request_start(self) -> None:
        with self._lock:
            self._requests_in_flight += 1

    def mark_request_end(
        self,
        *,
        method: str,
        status_code: int,
        duration_seconds: float,
        is_error: bool,
    ) -> None:
        with self._lock:
            self._requests_in_flight = max(0, self._requests_in_flight - 1)
            self._requests_total += 1
            self._total_duration_seconds += duration_seconds
            self._max_duration_seconds = max(
                self._max_duration_seconds, duration_seconds
            )
            self._last_request_at = datetime.now(UTC)
            self._requests_by_method[method] += 1
            self._responses_by_status[str(status_code)] += 1
            if is_error:
                self._errors_total += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            uptime_seconds = (datetime.now(UTC) - self.started_at).total_seconds()
            average_response_ms = (
                (self._total_duration_seconds / self._requests_total) * 1000
                if self._requests_total
                else 0.0
            )
            return {
                "service": self.service_name,
                "environment": self.environment,
                "uptime_seconds": round(uptime_seconds, 3),
                "started_at": self.started_at.isoformat(),
                "requests_total": self._requests_total,
                "requests_in_flight": self._requests_in_flight,
                "errors_total": self._errors_total,
                "average_response_time_ms": round(average_response_ms, 3),
                "max_response_time_ms": round(
                    self._max_duration_seconds * 1000, 3
                ),
                "last_request_at": (
                    self._last_request_at.isoformat()
                    if self._last_request_at is not None
                    else None
                ),
                "requests_by_method": dict(self._requests_by_method),
                "responses_by_status": dict(self._responses_by_status),
            }


def configure_logging(
    *,
    service_name: str,
    environment: str,
    log_level: str = "INFO",
    log_dir: str = "./logs",
    log_max_bytes: int = 5 * 1024 * 1024,
    log_backup_count: int = 5,
) -> logging.Logger:
    resolved_level = getattr(logging, log_level.upper(), logging.INFO)
    log_path = Path(log_dir).resolve()
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / f"{service_name}.log"
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s "
        "service=%(service_name)s env=%(environment)s "
        "request_id=%(request_id)s %(message)s"
    )
    root_logger = logging.getLogger()
    stream_handler_exists = False
    file_handler_exists = False

    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, RotatingFileHandler
        ):
            stream_handler_exists = True
        if isinstance(handler, RotatingFileHandler) and Path(
            handler.baseFilename
        ) == log_file:
            file_handler_exists = True

    if not stream_handler_exists:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    if not file_handler_exists:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=log_max_bytes,
            backupCount=log_backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    context_filter = RequestContextFilter(service_name, environment)
    for handler in root_logger.handlers:
        for existing_filter in tuple(handler.filters):
            if isinstance(existing_filter, RequestContextFilter):
                handler.removeFilter(existing_filter)
        handler.addFilter(context_filter)

    root_logger.setLevel(resolved_level)
    logging.captureWarnings(True)
    return logging.getLogger("app.observability")


def configure_observability(
    app: FastAPI,
    *,
    service_name: str,
    environment: str,
    log_level: str = "INFO",
    log_dir: str = "./logs",
    log_max_bytes: int = 5 * 1024 * 1024,
    log_backup_count: int = 5,
) -> None:
    logger = configure_logging(
        service_name=service_name,
        environment=environment,
        log_level=log_level,
        log_dir=log_dir,
        log_max_bytes=log_max_bytes,
        log_backup_count=log_backup_count,
    )
    metrics = MetricsRegistry(service_name=service_name, environment=environment)

    app.state.logger = logger
    app.state.metrics = metrics

    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        metrics.mark_request_start()
        token = request_id_context.set(request_id)
        start_time = perf_counter()
        status_code = 500
        failed_with_exception = False

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            failed_with_exception = True
            logger.exception(
                "request.failed method=%s path=%s",
                request.method,
                request.url.path,
            )
            raise
        finally:
            duration_seconds = perf_counter() - start_time
            metrics.mark_request_end(
                method=request.method,
                status_code=status_code,
                duration_seconds=duration_seconds,
                is_error=failed_with_exception or status_code >= 500,
            )
            if not failed_with_exception:
                log_method = logger.error if status_code >= 500 else logger.info
                log_method(
                    "request.completed method=%s path=%s status_code=%s duration_ms=%.2f",
                    request.method,
                    request.url.path,
                    status_code,
                    duration_seconds * 1000,
                )
            request_id_context.reset(token)

    @app.get("/metrics", tags=["system"])
    async def metrics_endpoint() -> JSONResponse:
        return JSONResponse(metrics.snapshot())
