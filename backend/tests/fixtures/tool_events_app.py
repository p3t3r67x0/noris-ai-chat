"""Local browser fixture: the real chat stack plus deterministic P1b handlers.

No execute route. Only this explicitly selected test app recognizes /p2-*.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import patch
from uuid import UUID, uuid5

import httpx
from fastapi import FastAPI
from sqlalchemy.engine import make_url

from noris_ai.chat.generation import GenerationManager, Peer
from noris_ai.chat.ws_protocol import GenerateIncomingMessage
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
from noris_ai.research.orchestrator import ResearchOrchestrator
from noris_ai.research.schemas import ResearchActivation
from noris_ai.tools.budget import BudgetAmount
from noris_ai.tools.cancellation import GenerationToolContext
from noris_ai.tools.errors import ToolError
from noris_ai.tools.models import ToolResult
from noris_ai.tools.policy import ToolPermission, ToolPolicy
from noris_ai.tools.providers.searxng import SearXNGProvider
from noris_ai.tools.providers.source_fetch import SourceFetchProvider, SourceFetchSettings
from noris_ai.tools.registry import (
    canonical_payload,
    create_tool_registry,
)
from noris_ai.tools.repository import ToolRepository
from noris_ai.tools.runtime import ToolRuntime
from noris_ai.tools.schemas import (
    FetchInput,
    SearchInput,
    SearchResult,
    SearchSource,
    ToolRunCreate,
)
from tests.fixtures.searxng_http import SearchServer
from tests.llm_integration.http_server import serve
from tests.llm_integration.test_http_search import config as search_config

config = Settings()
database_name = make_url(config.database_url.get_secret_value()).database
if config.environment != "test" or not database_name or not database_name.endswith("_test"):
    raise RuntimeError("Tool browser fixture requires an explicitly disposable test database")
app = create_app(config)
original_lifespan = app.router.lifespan_context


search_server = SearchServer()
committed_at: dict[str, float] = {}
fetch_calls = 0
research_sources: ContextVar[bool] = ContextVar("research_sources", default=False)


def source_response(request: httpx.Request) -> httpx.Response:
    global fetch_calls
    fetch_calls += 1
    return httpx.Response(
        200,
        headers={"Content-Type": "text/html"},
        stream=httpx.ByteStream(
            b"<main>"
            + b"P7a untrusted source text. " * (8 if research_sources.get() else 1)
            + b"</main>"
        ),
    )


class MeasuredRepository(ToolRepository):
    async def complete(
        self,
        owner_id: UUID,
        run_id: UUID,
        payload: bytes,
        *,
        execution_id: UUID | None = None,
        policy: ToolPolicy | None = None,
    ) -> ToolResult:
        result = await super().complete(
            owner_id, run_id, payload, execution_id=execution_id, policy=policy
        )
        committed_at[str(run_id)] = datetime.now(UTC).timestamp() * 1000
        return result


@app.get("/api/v1/fixture/search-state")
async def search_state() -> dict[str, object]:
    return {
        "calls": search_server.calls,
        "active": search_server.active,
        "committedAt": committed_at,
        "fetchCalls": fetch_calls,
    }


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    async with (
        original_lifespan(application),
        serve(search_server.app) as base_url,
        SearXNGProvider(search_config(base_url, config_version="p2-fixture")) as search_provider,
        SourceFetchProvider(
            SourceFetchSettings(), transport=httpx.MockTransport(source_response)
        ) as fetch_provider,
    ):

        async def resolve_source(context: GenerationToolContext, source_id: UUID) -> SearchSource:
            return await runtime.repository.resolve_source(context, source_id)

        registry = create_tool_registry(
            search_provider, source_fetch=fetch_provider, source_resolver=resolve_source
        )
        policy = ToolPolicy(
            {
                "web.search.v1": ToolPermission(
                    provider_key="searxng",
                    config_version="p2-fixture",
                    decision="allow",
                    per_call=BudgetAmount(calls=1, bytes=65_536),
                    daily_limit=BudgetAmount(calls=1000, bytes=65_536_000),
                    generation_limit=BudgetAmount(calls=6, bytes=2_097_152),
                ),
                "web.fetch.v1": ToolPermission(
                    provider_key="public_source",
                    config_version="p7a-v1",
                    decision="allow",
                    per_call=BudgetAmount(calls=1, bytes=262_144),
                    daily_limit=BudgetAmount(calls=1000, bytes=262_144_000),
                    generation_limit=BudgetAmount(calls=8, bytes=2_097_152),
                ),
            }
        )
        runtime = ToolRuntime(
            MeasuredRepository(application.state.chat_database, registry), registry, policy
        )
        manager = cast(GenerationManager, application.state.chat_generations)
        manager.tools = runtime
        application.state.chat_settings = config.model_copy(update={"research_enabled": True})
        application.state.chat_service.tools = runtime.repository
        manager.research = ResearchOrchestrator(
            config.model_copy(update={"research_enabled": True}),
            manager.repository,
            manager.gateway,
            runtime,
        )
        original_generate = manager.generate

        async def generate(peer: Peer, command: GenerateIncomingMessage) -> None:
            # Only this disposable test composition recognizes the marker. The
            # Public P7c intent uses the real server authorization below.
            activated = command.content.startswith("/p7b ") or command.research is not None
            token = research_sources.set(activated)
            try:
                await original_generate(
                    peer,
                    command,
                    research=ResearchActivation(config.chat_owner_id, "de")
                    if command.content.startswith("/p7b ") and command.research is None
                    else None,
                )
            finally:
                research_sources.reset(token)

        application.state.tool_runtime = runtime
        application.state.tool_repository = runtime.repository
        application.state.tool_registry = registry
        gateway = cast(LLMGateway, application.state.llm_gateway)
        original_events = gateway.events

        async def events(
            request: ChatRequest,
            *,
            before_stream: Callable[[], Awaitable[None]] | None = None,
        ) -> AsyncIterator[
            StartedEvent | DeltaEvent | CompletedEvent | IncompleteEvent | FailedEvent | None
        ]:
            prompt = request.messages[-1].content
            if prompt.startswith(("/p2-", "/p6-", "/p7a-", "/auto-limit p2-")):
                generation = UUID(request.generationId)

                async def execute(index: int) -> None:
                    invocation = ToolRunCreate(
                        id=uuid5(generation, f"p2-{index}"),
                        conversation_id=UUID(request.conversationId),
                        generation_id=generation,
                        step_key=f"p2-{index}",
                        tool_id="web.search.v1",
                        invocation_kind="web_mode",
                        provider_key="searxng",
                        config_version="p2-fixture",
                        deadline_at=datetime.now(UTC)
                        + timedelta(seconds=1 if prompt == "/p6-timeout" else 20),
                    )
                    with suppress(ToolError):
                        await runtime.execute(
                            config.chat_owner_id,
                            invocation,
                            canonical_payload(SearchInput(query=prompt, language="de")),
                        )
                    if prompt == "/p7a-fetch":
                        result = await runtime.repository.get_result(
                            config.chat_owner_id, invocation.id
                        )
                        if result is not None:
                            sources = SearchResult.model_validate_json(json.dumps(result.output))
                            fetch_run = invocation.model_copy(
                                update={
                                    "id": uuid5(generation, "p7a-fetch"),
                                    "step_key": "p7a-fetch",
                                    "tool_id": "web.fetch.v1",
                                    "provider_key": "public_source",
                                    "config_version": "p7a-v1",
                                    "source_search_run_id": invocation.id,
                                }
                            )
                            await runtime.execute(
                                config.chat_owner_id,
                                fetch_run,
                                canonical_payload(
                                    FetchInput(source_id=sources.sources[0].source_id)
                                ),
                            )

                await asyncio.gather(
                    *(execute(i) for i in range(2 if prompt == "/p2-parallel" else 1))
                )
            async for event in original_events(request, before_stream=before_stream):
                yield event

        try:
            with (
                patch.object(gateway, "events", events),
                patch.object(manager, "generate", generate),
            ):
                yield
        finally:
            await runtime.close()


app.router.lifespan_context = lifespan
