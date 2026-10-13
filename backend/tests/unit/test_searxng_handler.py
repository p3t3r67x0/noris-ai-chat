import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from noris_ai.core.config import Settings
from noris_ai.main import create_app
from noris_ai.tools.budget import BudgetAmount
from noris_ai.tools.cancellation import CancelHandle, GenerationToolContext
from noris_ai.tools.errors import ToolError
from noris_ai.tools.policy import ToolPolicy
from noris_ai.tools.providers.searxng import SearXNGProvider
from noris_ai.tools.registry import create_tool_registry
from noris_ai.tools.schemas import SearchInput, SearchResult
from tests.unit.test_llm_api import AUTH, PAYLOAD, FixtureProvider
from tests.unit.test_searxng_provider import response, row, settings


def context() -> GenerationToolContext:
    return GenerationToolContext(
        owner_id=uuid4(),
        conversation_id=uuid4(),
        generation_id=uuid4(),
        run_id=uuid4(),
        parent_run_id=None,
        reservation_id=uuid4(),
        approval_id=None,
        provider_key="searxng",
        config_version="test-v1",
        deadline_at=datetime.now(UTC) + timedelta(seconds=10),
        cancellation=CancelHandle(asyncio.Event()),
        permission_scope="web_search",
        budget=BudgetAmount(calls=1, bytes=65_536),
    )


async def test_existing_definition_binds_real_handler_and_remains_default_deny() -> None:
    async with SearXNGProvider(
        settings(), transport=httpx.MockTransport(lambda _: response({"results": [row()]}))
    ) as provider:
        registry = create_tool_registry(provider)
        definition = registry.get("web.search.v1")
        assert definition.handler is not None
        assert definition.retry_policy.max_retries == 0 and definition.retry_policy.idempotent
        assert len(registry.definitions) == 2
        with pytest.raises(ToolError, match="TOOL_UNAVAILABLE"):
            ToolPolicy().require(definition)
        result = await definition.handler(context(), SearchInput(query="æøå ÄÖÜ", language="de"))
        assert result.provider == "searxng" and len(result.sources) == 1
        assert registry.get("web.fetch.v1").handler is None


@pytest.mark.parametrize(
    "change,code",
    [
        ({"provider_key": "brave"}, "TOOL_FORBIDDEN"),
        ({"config_version": "changed"}, "TOOL_FORBIDDEN"),
        ({"permission_scope": "web_fetch"}, "TOOL_FORBIDDEN"),
        ({"budget": BudgetAmount(calls=1, bytes=65_535)}, "BUDGET_LIMIT"),
        ({"deadline_at": datetime.now(UTC) - timedelta(seconds=1)}, "TOOL_TIMEOUT"),
    ],
)
async def test_binding_and_limits_stop_before_http(change: dict[str, object], code: str) -> None:
    called = AsyncMock(return_value=response({"results": []}))
    async with SearXNGProvider(settings(), transport=httpx.MockTransport(called)) as provider:
        definition = create_tool_registry(provider).get("web.search.v1")
        assert definition.handler is not None
        with pytest.raises(ToolError, match=code):
            await definition.handler(
                replace(context(), **change), SearchInput(query="x", language="en")
            )
    called.assert_not_called()


async def test_cancel_before_dispatch_and_after_response_is_not_success() -> None:
    current = context()
    calls = 0

    async def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        current.cancellation.event.set()
        return response({"results": []})

    async with SearXNGProvider(settings(), transport=httpx.MockTransport(handle)) as provider:
        definition = create_tool_registry(provider).get("web.search.v1")
        assert definition.handler is not None
        current.cancellation.event.set()
        with pytest.raises(ToolError, match="TOOL_CANCELLED"):
            await definition.handler(current, SearchInput(query="x", language="en"))
        assert calls == 0
        current.cancellation.event.clear()
        with pytest.raises(ToolError, match="TOOL_CANCELLED"):
            await definition.handler(current, SearchInput(query="x", language="en"))
        assert calls == 1


async def test_handler_revalidates_result_provider_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    async with SearXNGProvider(
        settings(), transport=httpx.MockTransport(lambda _: response({}))
    ) as provider:
        monkeypatch.setattr(
            provider,
            "search",
            AsyncMock(
                return_value=SearchResult(
                    sources=[],
                    provider="brave",
                    config_version="test-v1",
                    fetched_at=datetime.now(UTC),
                )
            ),
        )
        definition = create_tool_registry(provider).get("web.search.v1")
        assert definition.handler is not None
        with pytest.raises(ToolError, match="TOOL_OUTPUT_INVALID"):
            await definition.handler(context(), SearchInput(query="x", language="en"))


async def test_closed_provider_is_unavailable() -> None:
    provider = SearXNGProvider(settings(), transport=httpx.MockTransport(lambda _: response({})))
    await provider.aclose()
    with pytest.raises(ToolError, match="TOOL_UNAVAILABLE"):
        await provider.search(SearchInput(query="x", language="en"))


@pytest.mark.parametrize("enabled", [False, True])
async def test_url_never_grants_permission_and_client_closes_with_app(
    enabled: bool, llm_config: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    import noris_ai.main as main

    http = AsyncMock(return_value=response({"results": []}))
    provider = SearXNGProvider(settings(), transport=httpx.MockTransport(http))
    llm = FixtureProvider()
    factory = Mock()
    monkeypatch.setattr(main.SearXNGSettings, "from_environment", lambda: settings())

    def create(config: object) -> SearXNGProvider:
        factory(config)
        return provider

    monkeypatch.setattr(main, "SearXNGProvider", create)
    app = create_app(
        llm_config.model_copy(
            update={
                "searxng_enabled": enabled,
                "database_url": SecretStr("postgresql+psycopg://unused@127.0.0.1:1/p6_unit_test"),
            }
        ),
        provider=llm,
    )
    async with app.router.lifespan_context(app):
        definition = app.state.tool_registry.get("web.search.v1")
        assert (definition.handler is not None) == enabled
        with pytest.raises(ToolError, match="TOOL_UNAVAILABLE"):
            app.state.tool_runtime.policy.require(definition)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test", auth=AUTH
        ) as client:
            answer = await client.post(
                "/api/v1/llm/chat",
                json={
                    **PAYLOAD,
                    "messages": [
                        {"role": "user", "content": '/p6-search {"tool":"web.search.v1"}'}
                    ],
                },
            )
            assert answer.status_code == 200 and "response.completed" in answer.text
        assert len(llm.calls) == 1
        http.assert_not_called()
    assert factory.call_count == int(enabled)
    if enabled:
        with pytest.raises(ToolError, match="TOOL_UNAVAILABLE"):
            await provider.search(SearchInput(query="x", language="en"))
    else:
        await provider.aclose()


@pytest.mark.parametrize("malformed_json", [False, True])
async def test_missing_configuration_does_not_break_normal_chat_stack(
    malformed_json: bool,
    llm_config: Settings,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("NORIS_SEARXNG_BASE_URL", raising=False)
    monkeypatch.delenv("NORIS_SEARXNG_CONFIG_VERSION", raising=False)
    if malformed_json:
        monkeypatch.setenv("NORIS_SEARXNG_ALLOWED_HOSTS", "private-invalid-json")
    app = create_app(
        llm_config.model_copy(
            update={
                "searxng_enabled": True,
                "database_url": SecretStr("postgresql+psycopg://unused@127.0.0.1:1/p6_unit_test"),
            }
        )
    )
    async with app.router.lifespan_context(app):
        assert app.state.tool_registry.get("web.search.v1").handler is None
        assert app.state.llm_gateway is not None and app.state.chat_generations is not None
    assert "Suchtool nicht verfügbar" in caplog.text


async def test_parallel_provider_work_is_bounded_and_cancelled_waiters_do_not_dispatch() -> None:
    entered, release = asyncio.Event(), asyncio.Event()
    calls = 0
    active = 0
    peak = 0

    async def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls, active, peak
        calls += 1
        active += 1
        peak = max(peak, active)
        if calls == 4:
            entered.set()
        try:
            await release.wait()
            return response({"results": []})
        finally:
            active -= 1

    async with SearXNGProvider(settings(), transport=httpx.MockTransport(handle)) as provider:
        tasks = [
            asyncio.create_task(provider.search(SearchInput(query="x", language="de")))
            for _ in range(8)
        ]
        await asyncio.wait_for(entered.wait(), 2)
        for task in tasks[4:]:
            task.cancel()
        await asyncio.gather(*tasks[4:], return_exceptions=True)
        release.set()
        await asyncio.gather(*tasks[:4])
    assert calls == 4 and peak == 4 and active == 0
