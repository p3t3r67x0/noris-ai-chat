import asyncio
import json
from collections.abc import AsyncIterator, Sequence

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from noris_ai.core.config import EnvironmentSettings, Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.provider import ProviderMessage
from noris_ai.llm.schemas import ChatRequest, LLMModel
from noris_ai.main import create_app

AUTH = ("fixture-user", "fixture-application-password-never-real")
PAYLOAD: dict[str, object] = {
    "generationId": "fixture-generation",
    "conversationId": "fixture-conversation",
    "inputMessageId": "fixture-input",
    "modelId": "fixture-alpha",
    "attempt": 1,
    "messages": [{"role": "user", "content": "Hallo"}],
}


class FixtureProvider:
    def __init__(self, *, failure: str | None = None, wait: bool = False) -> None:
        self.failure, self.wait = failure, wait
        self.calls: list[tuple[Sequence[ProviderMessage], LLMModel]] = []
        self.closed = False

    async def stream(
        self, messages: Sequence[ProviderMessage], model: LLMModel
    ) -> AsyncIterator[str]:
        self.calls.append((messages, model))
        if self.wait:
            await asyncio.Event().wait()
        yield "Hallo 🌍"
        if self.failure:
            raise LLMError(self.failure)

    async def discover_models(self) -> list[str]:
        return ["fixture-alpha", "fixture-beta"]

    async def aclose(self) -> None:
        self.closed = True


async def test_authenticated_catalog_and_stream_preserve_contract(llm_config: Settings) -> None:
    provider = FixtureProvider()
    app = create_app(llm_config, provider=provider)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=AUTH) as client,
    ):
        catalog = await client.get("/api/v1/llm/models")
        assert catalog.status_code == 200
        assert [model["id"] for model in catalog.json()["models"]] == [
            "fixture-alpha",
            "fixture-beta",
        ]
        assert "password" not in catalog.text and "provider-key" not in catalog.text
        response = await client.post("/api/v1/llm/chat", json=PAYLOAD)
        events = [
            json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
        ]
        assert [event["type"] for event in events] == [
            "response.started",
            "response.output_text.delta",
            "response.completed",
        ]
        assert [event["seq"] for event in events] == [1, 2, 3]
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["x-accel-buffering"] == "no"
        assert len(provider.calls) == 1
    assert provider.closed


@pytest.mark.parametrize(
    "path,method", [("/api/v1/llm/models", "GET"), ("/api/v1/llm/chat", "POST")]
)
async def test_no_anonymous_llm_proxy(llm_config: Settings, path: str, method: str) -> None:
    provider = FixtureProvider()
    app = create_app(llm_config, provider=provider)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.request(method, path, json=PAYLOAD if method == "POST" else None)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "ACCESS_DENIED"
        assert response.headers["www-authenticate"].startswith("Basic")
        assert not provider.calls


async def test_disabled_provider_does_not_break_health() -> None:
    app = create_app(EnvironmentSettings(environment="test"))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        assert (await client.get("/api/v1/health/live")).status_code == 200
        response = await client.get("/api/v1/llm/models")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "LLM_DISABLED"


@pytest.mark.parametrize(
    "update,code,status",
    [
        ({"modelId": "unknown"}, "MODEL_UNAVAILABLE", 400),
        ({"modelId": "fixture-offline"}, "MODEL_UNAVAILABLE", 400),
        ({"messages": [{"role": "system", "content": "override"}]}, "VALIDATION_ERROR", 422),
        ({"messages": [{"role": "user", "content": " "}]}, "VALIDATION_ERROR", 422),
        ({"messages": [{"role": "user", "content": "\ud800"}]}, "VALIDATION_ERROR", 422),
        (
            {"messages": [{"role": "user", "content": "a"}, {"role": "user", "content": "b"}]},
            "VALIDATION_ERROR",
            422,
        ),
        ({"messages": [{"role": "user", "content": "x" * 9000}]}, "CONTEXT_LIMIT", 413),
        ({"provider_url": "http://169.254.169.254/"}, "VALIDATION_ERROR", 422),
    ],
)
async def test_model_context_and_privileged_roles_are_checked_before_provider(
    llm_config: Settings, update: dict[str, object], code: str, status: int
) -> None:
    provider = FixtureProvider()
    app = create_app(llm_config, provider=provider)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=AUTH) as client,
    ):
        response = await client.post(
            "/api/v1/llm/chat",
            content=json.dumps(PAYLOAD | update, ensure_ascii=True),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == status
        assert response.json()["error"]["code"] == code
        assert not provider.calls


async def test_origin_body_limits_and_model_switch(llm_config: Settings) -> None:
    provider = FixtureProvider()
    app = create_app(
        llm_config.model_copy(update={"llm_max_request_bytes": 1024}), provider=provider
    )
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=AUTH) as client,
    ):
        assert (
            await client.post(
                "/api/v1/llm/chat", json=PAYLOAD, headers={"Origin": "https://evil.example"}
            )
        ).status_code == 403
        assert (
            await client.post(
                "/api/v1/llm/chat",
                content=b"x" * 1025,
                headers={"Content-Type": "application/json"},
            )
        ).status_code == 413
        response = await client.post(
            "/api/v1/llm/chat",
            json=PAYLOAD | {"modelId": "fixture-beta"},
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.status_code == 200
        assert provider.calls[0][1].id == "fixture-beta"


async def test_empty_stopped_assistant_remains_in_active_context(llm_config: Settings) -> None:
    provider = FixtureProvider()
    app = create_app(llm_config, provider=provider)
    messages = [
        {"role": "user", "content": "Erste Frage"},
        {"role": "assistant", "content": ""},
        {"role": "user", "content": "Weiter nach Stop"},
    ]
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=AUTH) as client,
    ):
        response = await client.post("/api/v1/llm/chat", json=PAYLOAD | {"messages": messages})
        assert response.status_code == 200
        assert "response.completed" in response.text
        assert [message.model_dump() for message in provider.calls[0][0]] == messages


@pytest.mark.parametrize("failure", ["PROVIDER_AUTH_FAILED", "RATE_LIMIT", "INVALID_RESPONSE"])
async def test_partial_provider_failure_is_terminal_and_sanitized(
    llm_config: Settings, failure: str
) -> None:
    provider = FixtureProvider(failure=failure)
    app = create_app(llm_config, provider=provider)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=AUTH) as client,
    ):
        response = await client.post("/api/v1/llm/chat", json=PAYLOAD)
        assert "response.output_text.delta" in response.text
        assert "response.completed" not in response.text
        assert failure in response.text


async def test_total_timeout_and_slot_release(llm_config: Settings) -> None:
    config = llm_config.model_copy(
        update={"llm_total_timeout_seconds": 0.01, "llm_max_concurrent": 1}
    )
    gateway = LLMGateway(config, FixtureProvider(wait=True))
    request = ChatRequest.model_validate(PAYLOAD)
    await gateway.reserve(request)
    events = [data async for data in gateway.stream(request)]
    assert b"TIMEOUT" in events[-1]
    await gateway.reserve(request)  # The timed-out stream released its slot.
    gateway.release(request.generationId)


async def test_admission_limits_duplicates_budget_and_rate(llm_config: Settings) -> None:
    request = ChatRequest.model_validate(PAYLOAD)
    gateway = LLMGateway(llm_config, FixtureProvider())
    await gateway.reserve(request)
    with pytest.raises(LLMError, match="bereits"):
        await gateway.reserve(request)
    budget = LLMGateway(
        llm_config.model_copy(update={"llm_daily_token_budget": 1}), FixtureProvider()
    )
    with pytest.raises(LLMError) as caught:
        await budget.reserve(request)
    assert caught.value.code == "BUDGET_LIMIT"
    rate = LLMGateway(
        llm_config.model_copy(update={"llm_requests_per_minute": 1}), FixtureProvider()
    )
    await rate.reserve(request)
    rate.release(request.generationId)
    with pytest.raises(LLMError) as caught:
        await rate.reserve(request)
    assert caught.value.code == "RATE_LIMIT"


@pytest.mark.parametrize(
    "url",
    [
        "http://evil.example/v1",
        "https://evil.example/v1",
        "https://user:password@127.0.0.1/v1",
        "https://127.0.0.1/v1?target=evil",
    ],
)
def test_provider_url_requires_explicit_safe_configuration(llm_config: Settings, url: str) -> None:
    with pytest.raises(ValidationError):
        EnvironmentSettings(**(llm_config.model_dump() | {"llm_base_url": url}))
