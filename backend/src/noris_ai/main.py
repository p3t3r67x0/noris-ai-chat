import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.exceptions import HTTPException

from noris_ai import __version__
from noris_ai.api.v1.conversations import router as conversations_router
from noris_ai.api.v1.health import router as health_router
from noris_ai.api.v1.llm import llm_error
from noris_ai.api.v1.llm import router as llm_router
from noris_ai.chat.errors import ChatError
from noris_ai.chat.repository import ChatRepository
from noris_ai.chat.service import ChatService
from noris_ai.core.config import Settings
from noris_ai.core.middleware import RequestContextMiddleware
from noris_ai.core.schemas import ErrorDetail, ErrorResponse
from noris_ai.db.readiness import DatabaseReadinessProbe, ReadinessProbe
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.limits import LLMRequestLimitMiddleware
from noris_ai.llm.openai_compatible import OpenAICompatibleProvider
from noris_ai.llm.provider import LLMProvider

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    probe: ReadinessProbe | None = None,
    provider: LLMProvider | None = None,
) -> FastAPI:
    config = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
        engine = create_async_engine(
            config.database_url.get_secret_value(), pool_pre_ping=True, pool_timeout=3
        )
        application.state.readiness_probe = (
            probe
            if probe is not None
            else DatabaseReadinessProbe(engine, config.readiness_timeout_seconds)
        )
        llm_provider = provider
        if llm_provider is None and config.llm_provider != "disabled":
            llm_provider = OpenAICompatibleProvider(config)
        application.state.llm_gateway = LLMGateway(config, llm_provider)
        database = async_sessionmaker(engine, expire_on_commit=False)
        repository = ChatRepository(database)
        application.state.chat_settings = config
        application.state.chat_database = database
        application.state.chat_repository = repository
        application.state.chat_service = ChatService(repository)
        # Startup recovery: generations orphaned by a restart are never
        # reported as completed.
        try:
            await repository.mark_running_generations_interrupted(config.chat_owner_id)
        except SQLAlchemyError:
            logger.warning("Could not mark interrupted generations at startup")
        try:
            yield
        finally:
            if llm_provider is not None:
                await llm_provider.aclose()
            await engine.dispose()

    application = FastAPI(
        title="noris AI API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/v1/docs" if config.environment != "production" else None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
    )

    application.add_middleware(LLMRequestLimitMiddleware, max_bytes=config.llm_max_request_bytes)
    application.add_middleware(RequestContextMiddleware)

    def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
        request_id = cast(UUID, getattr(request.state, "request_id", uuid4()))
        error = ErrorResponse(error=ErrorDetail(code=code, message=message, request_id=request_id))
        return JSONResponse(
            status_code=status,
            content=error.model_dump(mode="json"),
            headers={"X-Request-ID": str(request_id), "Cache-Control": "no-store"},
        )

    async def http_error(request: Request, exc: Exception) -> JSONResponse:
        http_exception = cast(HTTPException, exc)
        return error_response(
            request, http_exception.status_code, "HTTP_ERROR", "Request could not be processed"
        )

    async def validation_error(request: Request, exc: Exception) -> JSONResponse:
        return error_response(request, 422, "VALIDATION_ERROR", "Request validation failed")

    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        return error_response(request, 500, "INTERNAL_ERROR", "An internal error occurred")

    async def chat_error(request: Request, exc: Exception) -> JSONResponse:
        error = cast(ChatError, exc)
        headers = {"WWW-Authenticate": 'Basic realm="noris-ai-chat"'} if error.status == 401 else {}
        return JSONResponse(
            status_code=error.status,
            headers=headers,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=error.code,
                    message=error.message,
                    request_id=cast(UUID, request.state.request_id),
                )
            ).model_dump(mode="json"),
        )

    application.add_exception_handler(HTTPException, http_error)
    application.add_exception_handler(RequestValidationError, validation_error)
    application.add_exception_handler(Exception, internal_error)
    application.add_exception_handler(LLMError, llm_error)
    application.add_exception_handler(ChatError, chat_error)
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(llm_router, prefix="/api/v1")
    application.include_router(conversations_router, prefix="/api/v1")
    return application


app = create_app()
