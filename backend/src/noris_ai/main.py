from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.exceptions import HTTPException

from noris_ai import __version__
from noris_ai.api.v1.health import router as health_router
from noris_ai.core.config import Settings
from noris_ai.core.middleware import RequestContextMiddleware
from noris_ai.core.schemas import ErrorDetail, ErrorResponse
from noris_ai.db.readiness import DatabaseReadinessProbe, ReadinessProbe


def create_app(settings: Settings | None = None, probe: ReadinessProbe | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = create_async_engine(
            config.database_url.get_secret_value(), pool_pre_ping=True, pool_timeout=3
        )
        application.state.readiness_probe = (
            probe
            if probe is not None
            else DatabaseReadinessProbe(engine, config.readiness_timeout_seconds)
        )
        try:
            yield
        finally:
            await engine.dispose()

    application = FastAPI(
        title="noris AI API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/v1/docs" if config.environment != "production" else None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
    )

    application.add_middleware(RequestContextMiddleware)

    def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
        request_id = cast(UUID, getattr(request.state, "request_id", uuid4()))
        error = ErrorResponse(error=ErrorDetail(code=code, message=message, request_id=request_id))
        return JSONResponse(
            status_code=status,
            content=error.model_dump(mode="json"),
            headers={"X-Request-ID": str(request_id), "Cache-Control": "no-store"},
        )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return error_response(
            request, exc.status_code, "HTTP_ERROR", "Request could not be processed"
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(request, 422, "VALIDATION_ERROR", "Request validation failed")

    @application.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        return error_response(request, 500, "INTERNAL_ERROR", "An internal error occurred")

    application.include_router(health_router, prefix="/api/v1")
    return application


app = create_app()
