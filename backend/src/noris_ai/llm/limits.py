import asyncio
from uuid import UUID, uuid4

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from noris_ai.core.schemas import ErrorDetail, ErrorResponse
from noris_ai.llm.errors import LLMError


class LLMRequestLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self._app, self._max_bytes = app, max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or not scope["path"].startswith("/api/v1/llm/")
        ):
            await self._app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        error: LLMError | None = None
        if headers.get("content-type", "").split(";", 1)[0].strip() != "application/json":
            error = LLMError("INVALID_REQUEST", 415)
        body = bytearray()
        if error is None:
            try:
                async with asyncio.timeout(10):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        body.extend(message.get("body", b""))
                        if len(body) > self._max_bytes:
                            error = LLMError("REQUEST_TOO_LARGE", 413)
                            break
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                error = LLMError("TIMEOUT", 408)
        if error is not None:
            request_id = scope.get("state", {}).get("request_id", uuid4())
            if not isinstance(request_id, UUID):
                request_id = uuid4()
            response = JSONResponse(
                status_code=error.status,
                content=ErrorResponse(
                    error=ErrorDetail(code=error.code, message=error.message, request_id=request_id)
                ).model_dump(mode="json"),
            )
            await response(scope, receive, send)
            return
        delivered = False

        async def limited_receive() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self._app(scope, limited_receive, send)
