"""Loopback benchmark server; legacy reads reproduce main's eager API.

Never deploy this fixture. It refuses non-test databases and enabled providers.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import APIRouter, FastAPI
from sqlalchemy import event
from sqlalchemy.engine import make_url

from noris_ai.api.v1.conversations import ChatAccess
from noris_ai.chat.schemas import ConversationListResponse, MessageListResponse
from noris_ai.chat.service import conversation_response, message_response
from noris_ai.core.config import EnvironmentSettings
from noris_ai.main import create_app

settings = EnvironmentSettings()
database_name = make_url(settings.database_url.get_secret_value()).database
if not database_name or not database_name.endswith("_test") or settings.llm_provider != "disabled":
    raise RuntimeError("Benchmark requires a test database and disabled provider")
app = create_app(settings=settings)


@app.get("/fixture/metrics")
async def metrics() -> dict[str, int]:
    return {"queries": query_count}


query_count = 0
original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def measured_lifespan(application: FastAPI) -> AsyncIterator[None]:
    async with original_lifespan(application):
        engine = application.state.chat_database.kw["bind"]

        def query(*_args: object) -> None:
            global query_count
            query_count += 1

        event.listen(engine.sync_engine, "before_cursor_execute", query)
        yield


app.router.lifespan_context = measured_lifespan

if os.environ.get("NORIS_BENCHMARK_LEGACY") == "1":
    router = APIRouter()

    @router.get("/api/v1/conversations", response_model=ConversationListResponse)
    async def legacy_conversations(access: ChatAccess) -> ConversationListResponse:
        service, owner = access
        rows = await service.repository.list_conversations(owner, include_archived=True)
        return ConversationListResponse(conversations=[conversation_response(c) for c in rows])

    @router.get(
        "/api/v1/conversations/{conversation_id}/messages", response_model=MessageListResponse
    )
    async def legacy_messages(conversation_id: str, access: ChatAccess) -> MessageListResponse:
        service, owner = access
        rows = await service.repository.list_messages(owner, UUID(conversation_id))
        return MessageListResponse(messages=[message_response(m) for m in rows])

    app.router.routes = router.routes + app.router.routes
