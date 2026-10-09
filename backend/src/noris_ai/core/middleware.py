from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestContextMiddleware:
    """Attach request IDs without introducing buffering or extra tasks for future SSE."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_id = uuid4()
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_context(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = str(request_id)
                if "Cache-Control" not in headers:
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self._app(scope, receive, send_with_context)
