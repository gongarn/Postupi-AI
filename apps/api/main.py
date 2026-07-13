from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from apps.api.routes.internal import router as internal_router
from apps.api.routes.system import router as system_router
from packages.common.config import Settings, get_settings
from packages.common.logging import configure_logging
from packages.common.runtime import create_engine, create_redis


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    configure_logging(config.log_level)
    log = structlog.get_logger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        app.state.engine = create_engine(str(config.database_url))
        app.state.redis = create_redis(str(config.redis_url))
        log.info("api_started", environment=config.environment)
        try:
            yield
        finally:
            await app.state.redis.aclose()
            await app.state.engine.dispose()
            log.info("api_stopped")

    app = FastAPI(title="Postupi AI API", version="0.1.0", lifespan=lifespan)
    app.include_router(system_router)
    app.include_router(internal_router)

    @app.middleware("http")
    async def request_logging(request: Request, call_next: Any) -> Any:
        request_id = request.headers.get("x-request-id", str(uuid4()))
        start = perf_counter()
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        log.info(
            "http_request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round((perf_counter() - start) * 1000, 2),
        )
        return response

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", path=request.url.path, error_type=type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "internal server error"})

    return app


app = create_app()
