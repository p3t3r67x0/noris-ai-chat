import asyncio
import logging
from collections.abc import AsyncIterator
from secrets import compare_digest
from typing import Annotated, Any, cast
from uuid import UUID

import anyio
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import TypeAdapter
from starlette.types import Receive, Scope, Send

from noris_ai.core.schemas import ErrorDetail, ErrorResponse
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.schemas import (
    ChatRequest,
    ConversationTitleRequest,
    ConversationTitleResponse,
    ModelCatalog,
    StreamEvent,
)

router = APIRouter(prefix="/llm", tags=["LLM"])
security = HTTPBasic(auto_error=False, realm="noris-ai-chat")
logger = logging.getLogger(__name__)


async def access(
    request: Request, credentials: Annotated[HTTPBasicCredentials | None, Depends(security)]
) -> LLMGateway:
    gateway = cast(LLMGateway, request.app.state.llm_gateway)
    config = gateway.config
    if config.llm_provider == "disabled" or gateway.provider is None:
        raise LLMError("LLM_DISABLED", 503)
    password = config.llm_access_password
    username_ok = compare_digest(
        (credentials.username if credentials else "").encode(), config.llm_access_username.encode()
    )
    password_ok = compare_digest(
        (credentials.password if credentials else "").encode(),
        (password.get_secret_value() if password else "").encode(),
    )
    if not (credentials and username_ok and password_ok):
        raise LLMError("ACCESS_DENIED", 401)
    if request.method == "POST":
        origin = request.headers.get("origin")
        if origin is not None and origin not in config.llm_allowed_origins:
            raise LLMError("ORIGIN_DENIED", 403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise LLMError("ORIGIN_DENIED", 403)
    return gateway


async def llm_error(request: Request, exc: Exception) -> JSONResponse:
    error = cast(LLMError, exc)
    headers = {"WWW-Authenticate": 'Basic realm="noris-ai-chat"'} if error.status == 401 else {}
    if error.status == 429:
        headers["Retry-After"] = "60"
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


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse}
    for code in (400, 401, 403, 408, 409, 413, 415, 422, 429, 500, 503)
}
EVENT_SCHEMA = TypeAdapter(StreamEvent).json_schema(ref_template="#/components/schemas/{model}")
EVENT_SCHEMA.pop("$defs", None)  # FastAPI collects these from response_model.


@router.get(
    "/models", operation_id="getLLMModels", response_model=ModelCatalog, responses=ERROR_RESPONSES
)
async def models(gateway: Annotated[LLMGateway, Depends(access)]) -> ModelCatalog:
    return ModelCatalog(
        models=[
            model for model in gateway.config.llm_models if model.available and model.streaming
        ],
        default_model=gateway.config.llm_default_model,
    )


@router.post(
    "/conversation-title",
    operation_id="generateConversationTitle",
    response_model=ConversationTitleResponse,
    responses=ERROR_RESPONSES | {502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
)
async def conversation_title(
    payload: ConversationTitleRequest,
    request: Request,
    gateway: Annotated[LLMGateway, Depends(access)],
) -> ConversationTitleResponse:
    async def disconnected() -> None:
        while (await request.receive())["type"] != "http.disconnect":
            pass

    generation = asyncio.create_task(gateway.conversation_title(payload))
    disconnect = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait({generation, disconnect}, return_when=asyncio.FIRST_COMPLETED)
        if generation in done:
            return await generation
        raise LLMError("STREAM_INTERRUPTED")
    except LLMError as error:
        # Fixed diagnostic code only: no prompt, title, identifiers or exception body.
        logger.info("Conversation title generation failed: %s", error.code)
        raise
    finally:
        generation.cancel()
        disconnect.cancel()
        await asyncio.gather(generation, disconnect, return_exceptions=True)


class SSEStreamingResponse(StreamingResponse):
    media_type = "text/event-stream"

    def __init__(
        self, iterator: AsyncIterator[bytes], gateway: LLMGateway, generation_id: str
    ) -> None:
        super().__init__(
            iterator,
            media_type=self.media_type,
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store, no-transform"},
        )
        self._iterator, self._gateway, self._generation_id = iterator, gateway, generation_id

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Always listen for disconnect, including ASGI 2.4+ during a quiet upstream.
        try:
            async with anyio.create_task_group() as group:

                async def run_stream() -> None:
                    await self.stream_response(send)
                    group.cancel_scope.cancel()

                group.start_soon(run_stream)
                await self.listen_for_disconnect(receive)
                group.cancel_scope.cancel()
        finally:
            with anyio.CancelScope(shield=True):
                close = getattr(self._iterator, "aclose", None)
                if close is not None:
                    await close()
                self._gateway.release(self._generation_id)


@router.post(
    "/chat",
    operation_id="streamChat",
    status_code=200,
    response_model=StreamEvent,
    response_class=SSEStreamingResponse,
    responses=ERROR_RESPONSES | {200: {"content": {"text/event-stream": {"schema": EVENT_SCHEMA}}}},
)
async def chat(
    payload: ChatRequest, gateway: Annotated[LLMGateway, Depends(access)]
) -> SSEStreamingResponse:
    gateway.reserve(payload)
    return SSEStreamingResponse(gateway.stream(payload), gateway, payload.generationId)
