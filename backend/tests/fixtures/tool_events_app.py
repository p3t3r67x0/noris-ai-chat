"""Local browser fixture: the real chat stack plus deterministic P1b handlers.

No execute route. Only this explicitly selected test app recognizes /p2-*.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import patch
from uuid import UUID, uuid5

from fastapi import FastAPI
from pydantic import HttpUrl
from sqlalchemy.engine import make_url

from noris_ai.chat.generation import GenerationManager
from noris_ai.core.config import Settings
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.schemas import (
    ChatRequest,
    CompletedEvent,
    DeltaEvent,
    FailedEvent,
    IncompleteEvent,
    StartedEvent,
)
from noris_ai.main import create_app
from noris_ai.tools.budget import BudgetAmount
from noris_ai.tools.cancellation import GenerationToolContext
from noris_ai.tools.errors import ToolError
from noris_ai.tools.policy import ToolPermission, ToolPolicy
from noris_ai.tools.registry import (
    RetryPolicy,
    ToolRegistry,
    canonical_payload,
    create_tool_registry,
)
from noris_ai.tools.repository import ToolRepository
from noris_ai.tools.runtime import ToolRuntime
from noris_ai.tools.schemas import SearchInput, SearchResult, SearchSource, ToolRunCreate

config = Settings()
database_name = make_url(config.database_url.get_secret_value()).database
if config.environment != "test" or not database_name or not database_name.endswith("_test"):
    raise RuntimeError("Tool browser fixture requires an explicitly disposable test database")
app = create_app(config)
original_lifespan = app.router.lifespan_context


async def handler(context: GenerationToolContext, value: SearchInput) -> SearchResult:
    await asyncio.sleep(3 if value.query == "/p2-slow" else 0.8)
    context.check()
    if value.query == "/p2-error":
        raise ToolError("PROVIDER_ERROR")
    return SearchResult(
        sources=[
            SearchSource(
                source_id=uuid5(context.run_id, str(i)),
                title=f"Fixture source {i}",
                url=HttpUrl(f"https://example.org/fixture/{i}"),
                snippet="Deterministic local fixture",
            )
            for i in range(5)
        ],
        provider="searxng",
        config_version="p2-fixture",
        fetched_at=datetime.now(UTC),
    )


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    async with original_lifespan(application):
        registry = ToolRegistry(
            (
                replace(
                    create_tool_registry().get("web.search.v1"),
                    handler=handler,
                    provider_key="p2-fixture",
                    cost_policy="bounded",
                    retry_policy=RetryPolicy(0, True),
                ),
            )
        )
        policy = ToolPolicy(
            {
                "web.search.v1": ToolPermission(
                    provider_key="p2-fixture",
                    config_version="p2-fixture",
                    decision="allow",
                    per_call=BudgetAmount(calls=1, bytes=4096),
                    daily_limit=BudgetAmount(calls=1000, bytes=4_096_000),
                    generation_limit=BudgetAmount(calls=4, bytes=16_384),
                )
            }
        )
        runtime = ToolRuntime(
            ToolRepository(application.state.chat_database, registry), registry, policy
        )
        manager = cast(GenerationManager, application.state.chat_generations)
        manager.tools = runtime
        application.state.tool_runtime = runtime
        application.state.tool_repository = runtime.repository
        gateway = cast(LLMGateway, application.state.llm_gateway)
        original_events = gateway.events

        async def events(
            request: ChatRequest,
        ) -> AsyncIterator[
            StartedEvent | DeltaEvent | CompletedEvent | IncompleteEvent | FailedEvent | None
        ]:
            prompt = request.messages[-1].content
            if prompt.startswith("/p2-"):
                generation = UUID(request.generationId)

                async def execute(index: int) -> None:
                    invocation = ToolRunCreate(
                        id=uuid5(generation, f"p2-{index}"),
                        conversation_id=UUID(request.conversationId),
                        generation_id=generation,
                        step_key=f"p2-{index}",
                        tool_id="web.search.v1",
                        invocation_kind="web_mode",
                        provider_key="p2-fixture",
                        config_version="p2-fixture",
                        deadline_at=datetime.now(UTC) + timedelta(seconds=20),
                    )
                    with suppress(ToolError):
                        await runtime.execute(
                            config.chat_owner_id,
                            invocation,
                            canonical_payload(SearchInput(query=prompt, language="de")),
                        )

                await asyncio.gather(
                    *(execute(i) for i in range(2 if prompt == "/p2-parallel" else 1))
                )
            async for event in original_events(request):
                yield event

        try:
            with patch.object(gateway, "events", events):
                yield
        finally:
            await runtime.close()


app.router.lifespan_context = lifespan
