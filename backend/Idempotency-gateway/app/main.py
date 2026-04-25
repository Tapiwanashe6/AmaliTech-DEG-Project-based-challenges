from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.logger import get_logger, setup_logging
from app.routes.payment import router as payment_router
from app.state.machine import state_manager


log = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = req_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


def create_app() -> FastAPI:
    setup_logging()
    settings = get_settings()

    app = FastAPI(
        title="Idempotency-Gateway (Pipeline Architecture)",
        version="1.0.0",
        description="State-machine based idempotent payment gateway using a middleware pipeline.",
    )
    app.state.sweeper_task = None

    app.add_middleware(RequestContextMiddleware)

    @app.on_event("startup")
    async def _startup() -> None:
        log.info(
            "server.start",
            extra={
                "port": settings.port,
                "env": settings.app_env,
                "ttlSeconds": settings.idempotency_ttl_seconds,
                "sweepIntervalSeconds": settings.idempotency_sweep_interval_seconds,
                "simulatedDelaySeconds": settings.payment_simulated_delay_seconds,
            },
        )
        app.state.sweeper_task = asyncio.create_task(
            _sweeper(settings.idempotency_sweep_interval_seconds, settings.idempotency_ttl_seconds)
        )

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        log.info("server.shutdown", extra={})
        task: Optional[asyncio.Task] = app.state.sweeper_task
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "idempotencyEntries": len(state_manager._store),
        }

    app.include_router(payment_router)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "http_error", "message": str(exc.detail)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content={
                "error": "validation_error",
                "message": "; ".join(
                    f"{'.'.join(str(x) for x in e.get('loc', ()))}: {e.get('msg', 'invalid')}"
                    for e in exc.errors()
                ),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        log.exception(
            "unhandled_error",
            extra={
                "requestId": getattr(request.state, "request_id", None),
                "path": request.url.path,
                "method": request.method,
            },
        )
        is_prod = get_settings().app_env == "production"
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred" if is_prod else str(exc),
            },
        )

    return app


async def _sweeper(interval_seconds: float, ttl_seconds: float) -> None:
    try:
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                state_manager.sweep_expired(ttl_seconds)
            except Exception:
                log.exception("sweep_failed", extra={})
    except asyncio.CancelledError:
        raise


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=(settings.app_env == "development"),
        log_config=None,
    )
