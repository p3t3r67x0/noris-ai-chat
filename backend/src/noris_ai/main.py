import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from pydantic_settings import SettingsError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.exceptions import HTTPException

from noris_ai import __version__
from noris_ai.api.v1.attachments import router as attachments_router
from noris_ai.api.v1.chat_ws import router as chat_ws_router
from noris_ai.api.v1.conversations import router as conversations_router
from noris_ai.api.v1.health import router as health_router
from noris_ai.api.v1.llm import llm_error
from noris_ai.api.v1.llm import router as llm_router
from noris_ai.api.v1.tools import router as tools_router
from noris_ai.chat.attachments import AttachmentService
from noris_ai.chat.errors import ChatError
from noris_ai.chat.generation import GenerationManager
from noris_ai.chat.repository import ChatRepository
from noris_ai.chat.service import ChatService
from noris_ai.chat.tickets import WsTicketStore
from noris_ai.core.config import Settings
from noris_ai.core.middleware import RequestContextMiddleware
from noris_ai.core.schemas import ErrorDetail, ErrorResponse
from noris_ai.db.readiness import DatabaseReadinessProbe, ReadinessProbe
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.limits import LLMRequestLimitMiddleware
from noris_ai.llm.openai_compatible import OpenAICompatibleProvider
from noris_ai.llm.provider import LLMProvider
from noris_ai.tools.budget import BudgetCoordinator
from noris_ai.tools.cancellation import GenerationToolContext
from noris_ai.tools.errors import ToolError
from noris_ai.tools.policy import ToolPolicy
from noris_ai.tools.providers.searxng import SearXNGProvider, SearXNGSettings
from noris_ai.tools.providers.source_fetch import SourceFetchProvider, SourceFetchSettings
from noris_ai.tools.registry import create_tool_registry
from noris_ai.tools.repository import ToolRepository
from noris_ai.tools.runtime import ToolRuntime
from noris_ai.tools.schemas import SearchSource

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    probe: ReadinessProbe | None = None,
    provider: LLMProvider | None = None,
) -> FastAPI:
    config = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
        search_provider = None
        if config.searxng_enabled:
            try:
                search_provider = SearXNGProvider(SearXNGSettings.from_environment())
            except (ValidationError, SettingsError):
                logger.warning("SearXNG-Konfiguration ungültig; Suchtool nicht verfügbar")
        fetch_provider = None
        if config.source_fetch_enabled:
            try:
                fetch_provider = SourceFetchProvider(SourceFetchSettings())
            except (ValidationError, SettingsError):
                logger.warning("Source-Fetch-Konfiguration ungültig; Fetchtool nicht verfügbar")

        async def resolve_source(context: GenerationToolContext, source_id: UUID) -> SearchSource:
            return await tool_repository.resolve_source(context, source_id)

        tool_registry = create_tool_registry(
            search_provider, source_fetch=fetch_provider, source_resolver=resolve_source
        )
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
        database = async_sessionmaker(engine, expire_on_commit=False)
        budget = BudgetCoordinator(database)
        application.state.llm_gateway = LLMGateway(config, llm_provider, budget)
        repository = ChatRepository(database)
        application.state.chat_settings = config
        application.state.chat_database = database
        application.state.chat_repository = repository
        application.state.tool_registry = tool_registry
        tool_repository = ToolRepository(database, tool_registry)
        application.state.tool_repository = tool_repository
        tool_runtime = ToolRuntime(tool_repository, tool_registry, ToolPolicy())
        application.state.tool_runtime = tool_runtime
        attachments = AttachmentService(config, database)
        application.state.chat_attachments = attachments
        application.state.chat_service = ChatService(repository)
        application.state.chat_tickets = WsTicketStore(config.chat_ws_ticket_ttl_seconds)
        application.state.chat_generations = GenerationManager(
            config, repository, application.state.llm_gateway, attachments, tool_runtime
        )
        # Startup recovery: generations orphaned by a restart are never
        # reported as completed.
        database_available = True
        try:
            await tool_runtime.repository.recover(config.chat_owner_id)
            await budget.recover_text(config.chat_owner_id)
            await repository.mark_running_generations_interrupted(config.chat_owner_id)
        except SQLAlchemyError:
            database_available = False
            logger.warning("Could not mark interrupted generations at startup")

        shutting_down = asyncio.Event()

        async def clean_attachments() -> None:
            if not database_available:
                await asyncio.sleep(3600)
            while not shutting_down.is_set():
                try:
                    async with asyncio.timeout(5):
                        await attachments.cleanup()
                except (SQLAlchemyError, OSError, TimeoutError):
                    logger.warning("Could not clean expired attachments")
                # A database driver can wrap cancellation in SQLAlchemyError.
                # Never sleep again once the application has begun shutdown.
                if not shutting_down.is_set():
                    await asyncio.sleep(3600)

        cleanup = asyncio.create_task(clean_attachments())

        async def clean_tools() -> None:
            while not shutting_down.is_set():
                if database_available:
                    try:
                        async with asyncio.timeout(5):
                            await tool_runtime.repository.expire_pending(config.chat_owner_id)
                    except (SQLAlchemyError, TimeoutError):
                        logger.warning("Could not expire pending tool runs")
                await asyncio.sleep(1)

        tool_cleanup = asyncio.create_task(clean_tools())
        try:
            yield
        finally:
            shutting_down.set()
            cleanup.cancel()
            tool_cleanup.cancel()
            await asyncio.gather(cleanup, tool_cleanup, return_exceptions=True)
            await application.state.chat_generations.close()
            await tool_runtime.close()
            if search_provider is not None:
                await search_provider.aclose()
            if fetch_provider is not None:
                await fetch_provider.aclose()
            if database_available:
                await tool_runtime.repository.recover(config.chat_owner_id)
                await budget.recover_text(config.chat_owner_id)
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

    async def tool_error(request: Request, exc: Exception) -> JSONResponse:
        error = cast(ToolError, exc)
        return error_response(request, error.status, error.code, error.message)

    application.add_exception_handler(HTTPException, http_error)
    application.add_exception_handler(RequestValidationError, validation_error)
    application.add_exception_handler(Exception, internal_error)
    application.add_exception_handler(LLMError, llm_error)
    application.add_exception_handler(ChatError, chat_error)
    application.add_exception_handler(ToolError, tool_error)
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(llm_router, prefix="/api/v1")
    application.include_router(conversations_router, prefix="/api/v1")
    application.include_router(chat_ws_router, prefix="/api/v1")
    application.include_router(attachments_router, prefix="/api/v1")
    application.include_router(tools_router, prefix="/api/v1")
    return application


app = create_app()
