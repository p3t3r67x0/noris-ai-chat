import asyncio
import json
from collections.abc import AsyncIterator, Sequence

import httpx
import pytest

from noris_ai.core.config import EnvironmentSettings, Settings
from noris_ai.llm.catalog import ModelCatalogService
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.openai_compatible import OpenAICompatibleProvider
from noris_ai.llm.provider import ProviderMessage
from noris_ai.llm.registry import REGISTRY, chat_compatible, classify
from noris_ai.llm.schemas import ChatRequest, LLMModel
from noris_ai.main import create_app

GPT = "vllm/release/gpt-oss-120b"
GEMMA = "vllm/release/gemma-4-31b-it"
GLM = "vllm/release/glm-5-2"


class CatalogProvider:
    def __init__(self) -> None:
        self.ids = [GPT, GEMMA, "smart_router"]
        self.discovery_calls = 0
        self.error: LLMError | None = None
        self.generations: list[LLMModel] = []

    async def discover_models(self) -> list[str]:
        self.discovery_calls += 1
        await asyncio.sleep(0)
        if self.error:
            raise self.error
        return self.ids

    async def stream(
        self, messages: Sequence[ProviderMessage], model: LLMModel
    ) -> AsyncIterator[str]:
        self.generations.append(model)
        yield "Hallo"

    async def aclose(self) -> None:
        pass


def request(model_id: str) -> ChatRequest:
    return ChatRequest.model_validate(
        {
            "generationId": "catalog-generation",
            "conversationId": "catalog-chat",
            "inputMessageId": "catalog-input",
            "modelId": model_id,
            "attempt": 1,
            "messages": [{"role": "user", "content": "Hallo"}],
        }
    )


async def test_filters_exact_ids_and_requires_router_entitlement(llm_config: Settings) -> None:
    provider = CatalogProvider()
    provider.ids += [
        "new-chat-model",
        *[model.id for model in REGISTRY.values() if model.category in ("EMBEDDING", "RERANKING")],
    ]
    catalog = ModelCatalogService(llm_config, provider)
    result = await catalog.get()
    assert [model.id for model in result.models] == ["smart_router", GEMMA, GPT]
    assert result.models[0].name == "Automatisch"
    assert result.models[0].virtual
    assert result.default_model == "smart_router"
    unknown = classify("new-chat-model", ())
    assert unknown.category == "UNKNOWN" and not chat_compatible(unknown)
    assert classify("gpt-oss-120b", ()).category == "UNKNOWN"
    catalog.invalidate()
    provider.ids.remove("smart_router")
    assert all(model.id != "smart_router" for model in (await catalog.get()).models)


async def test_empty_replaces_catalog_and_revoked_model_cannot_generate(
    llm_config: Settings,
) -> None:
    provider = CatalogProvider()
    gateway = LLMGateway(llm_config, provider)
    await gateway.reserve(request(GPT))
    gateway.release("catalog-generation")
    gateway.catalog.invalidate()
    provider.ids = []
    catalog = await gateway.catalog.get()
    assert catalog.models == [] and catalog.default_model is None
    with pytest.raises(LLMError, match="nicht verfügbar"):
        await gateway.reserve(request(GPT))
    assert provider.generations == []


async def test_ttl_single_flight_and_revocation(llm_config: Settings) -> None:
    provider = CatalogProvider()
    now = [0.0]
    catalog = ModelCatalogService(llm_config, provider, lambda: now[0])
    results = await asyncio.gather(*(catalog.get() for _ in range(20)))
    assert len(results) == 20 and provider.discovery_calls == 1
    now[0] = 299
    assert (await catalog.require(GPT)).id == GPT
    assert provider.discovery_calls == 1
    provider.ids.remove(GPT)
    now[0] = 300
    with pytest.raises(LLMError):
        await catalog.require(GPT)
    assert provider.discovery_calls == 2


@pytest.mark.parametrize("code", ["TIMEOUT", "PROVIDER_AUTH_FAILED", "PROVIDER_UNREACHABLE"])
async def test_failures_coalesce_and_never_authorize_stale(llm_config: Settings, code: str) -> None:
    provider = CatalogProvider()
    now = [0.0]
    config = llm_config.model_copy(update={"llm_catalog_stale_seconds": 30})
    catalog = ModelCatalogService(config, provider, lambda: now[0])
    await catalog.get()
    now[0] = 300
    provider.error = LLMError(code)
    results = await asyncio.gather(*(catalog.get() for _ in range(10)), return_exceptions=True)
    assert provider.discovery_calls == 2
    if code != "PROVIDER_AUTH_FAILED":
        stale = await catalog.get()
        assert stale.status == "stale" and stale.default_model is None
        assert all(not model.available for model in stale.models)
    else:
        assert all(isinstance(value, LLMError) for value in results)
    with pytest.raises(LLMError):
        await catalog.require(GPT)
    now[0] = 331
    with pytest.raises(LLMError):
        await catalog.get()
    provider.error = None
    now[0] = 342
    assert (await catalog.get()).status == "fresh"


async def test_default_stale_policy_is_closed(llm_config: Settings) -> None:
    provider = CatalogProvider()
    now = [0.0]
    catalog = ModelCatalogService(llm_config, provider, lambda: now[0])
    await catalog.get()
    now[0] = 301
    provider.error = LLMError("PROVIDER_ERROR")
    with pytest.raises(LLMError):
        await catalog.get()


async def test_dynamic_catalog_respects_application_output_and_stream_limits(
    llm_config: Settings,
) -> None:
    provider = CatalogProvider()
    config = llm_config.model_copy(
        update={
            "llm_max_output_tokens": 512,
            "llm_max_response_chars": 100_000,
            "llm_max_continuations": 2,
        }
    )
    gateway = LLMGateway(config, provider)
    catalog = await gateway.catalog.get()
    assert all(model.max_output_tokens == 512 for model in catalog.models)
    assert catalog.limits.max_message_chars == config.llm_max_message_chars
    assert catalog.limits.max_response_chars == 100_000
    assert catalog.limits.max_stream_bytes == config.llm_max_stream_bytes
    assert catalog.limits.max_continuations == 2
    assert catalog.limits.stream_timeout_ms == int(config.llm_total_timeout_seconds * 1000) + 15_000
    await gateway.reserve(request(GPT))
    _ = [event async for event in gateway.stream(request(GPT))]
    assert provider.generations[0].max_output_tokens == 512


async def test_continuation_obeys_dynamic_model_admission_and_revocation(
    llm_config: Settings,
) -> None:
    provider = CatalogProvider()
    gateway = LLMGateway(llm_config, provider)
    payload = ChatRequest.model_validate(
        request(GPT).model_dump()
        | {
            "operation": "continue",
            "assistantMessageId": "existing-answer",
            "continuationCount": 1,
            "messages": [
                {"role": "user", "content": "Hallo"},
                {"role": "assistant", "content": "Bestehende Antwort"},
            ],
        }
    )
    await gateway.reserve(payload)
    events = b"".join([event async for event in gateway.stream(payload)])
    assert b"response.completed" in events
    assert provider.generations[0].id == GPT
    gateway.catalog.invalidate()
    provider.ids = []
    with pytest.raises(LLMError) as revoked:
        await gateway.reserve(payload.model_copy(update={"generationId": "next-continuation"}))
    assert revoked.value.code == "MODEL_UNAVAILABLE"
    assert len(provider.generations) == 1


async def test_concurrent_continuations_lock_the_answer_after_catalog_discovery(
    llm_config: Settings,
) -> None:
    provider = CatalogProvider()
    gateway = LLMGateway(llm_config, provider)
    payload = ChatRequest.model_validate(
        request(GPT).model_dump()
        | {
            "operation": "continue",
            "assistantMessageId": "existing-answer",
            "continuationCount": 1,
            "messages": [
                {"role": "user", "content": "Hallo"},
                {"role": "assistant", "content": "Bestehende Antwort"},
            ],
        }
    )
    results = await asyncio.gather(
        gateway.reserve(payload),
        gateway.reserve(payload.model_copy(update={"generationId": "parallel-continuation"})),
        return_exceptions=True,
    )
    assert sum(result is None for result in results) == 1
    assert [result.code for result in results if isinstance(result, LLMError)] == [
        "GENERATION_ACTIVE"
    ]
    assert provider.discovery_calls == 1
    gateway.release(payload.generationId)
    gateway.release("parallel-continuation")


@pytest.mark.parametrize(
    "data,expected",
    [
        (
            {
                "data": [
                    {"id": GPT, "unexpected": {"streaming": False}},
                    {"id": "smart_router"},
                    {"id": 42},
                    {},
                    None,
                    {"id": "https://bad/?q=x"},
                    {"id": GPT},
                    {"id": GEMMA, "is_ready": False},
                    {"id": GLM, "is_ready": "true"},
                ]
            },
            [GPT, "smart_router"],
        ),
        ({"object": "list", "data": []}, []),
    ],
)
async def test_discovery_tolerates_extra_missing_and_unknown_fields(
    llm_config: Settings,
    data: dict[str, object],
    expected: list[str],
) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=data)

    provider = OpenAICompatibleProvider(llm_config, transport=httpx.MockTransport(handler))
    try:
        assert await provider.discover_models() == expected
        assert str(captured[0].url) == str(llm_config.llm_base_url) + "/models"
        assert captured[0].headers["authorization"] == "Bearer fixture-provider-key-never-real"
    finally:
        await provider.aclose()


@pytest.mark.parametrize("payload", [{}, {"data": None}, {"data": {}}, [GPT]])
async def test_discovery_rejects_invalid_envelope(llm_config: Settings, payload: object) -> None:
    provider = OpenAICompatibleProvider(
        llm_config, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    )
    try:
        with pytest.raises(LLMError) as raised:
            await provider.discover_models()
        assert raised.value.code == "INVALID_RESPONSE"
    finally:
        await provider.aclose()


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "PROVIDER_AUTH_FAILED"),
        (403, "PROVIDER_AUTH_FAILED"),
        (500, "PROVIDER_ERROR"),
        (302, "PROVIDER_ERROR"),
        (429, "RATE_LIMIT"),
    ],
)
async def test_discovery_http_errors_are_sanitized(
    llm_config: Settings, status: int, code: str
) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(status, text="secret", headers={"Location": "https://evil.example"})

    provider = OpenAICompatibleProvider(llm_config, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(LLMError) as raised:
            await provider.discover_models()
        assert raised.value.code == code and "secret" not in str(raised.value)
        assert len(captured) == 1
    finally:
        await provider.aclose()


async def test_discovery_timeout_is_bounded(llm_config: Settings) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        await asyncio.Event().wait()
        return httpx.Response(200, json={"data": []})

    config = llm_config.model_copy(update={"llm_discovery_timeout_seconds": 0.01})
    provider = OpenAICompatibleProvider(config, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(LLMError) as raised:
            await provider.discover_models()
        assert raised.value.code == "TIMEOUT"
    finally:
        await provider.aclose()


async def test_api_catalog_and_chat_share_admission(llm_config: Settings) -> None:
    provider = CatalogProvider()
    app = create_app(llm_config, provider=provider)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            auth=("fixture-user", "fixture-application-password-never-real"),
        ) as client,
    ):
        catalog = await client.get("/api/v1/llm/models")
        assert catalog.status_code == 200 and GPT in catalog.text
        denied = await client.post("/api/v1/llm/chat", json=request("new-model").model_dump())
        assert denied.status_code == 400 and not provider.generations
        granted = await client.post("/api/v1/llm/chat", json=request(GPT).model_dump())
        assert "response.completed" in granted.text
        assert provider.discovery_calls == 1
        assert "fixture-provider-key" not in catalog.text


async def test_model_specific_token_and_reasoning_parameters(llm_config: Settings) -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=(
                b'data: {"choices":[{"index":0,"delta":{"content":"Hi"},'
                b'"finish_reason":"stop"}]}\n\n'
                b"data: [DONE]\n\n"
            ),
        )

    config = llm_config.model_copy(update={"llm_reasoning_effort": "high"})
    provider = OpenAICompatibleProvider(config, transport=httpx.MockTransport(handler))
    models = [
        REGISTRY[GPT].model_copy(update={"reasoning_effort": "low"}),
        REGISTRY[GEMMA],
        REGISTRY[GLM].model_copy(update={"reasoning_effort": "max"}),
        llm_config.llm_models[1].model_copy(
            update={"token_limit_parameter": "max_completion_tokens", "max_output_tokens": 512}
        ),
    ]
    try:
        for model in models:
            assert [text async for text in provider.stream(request(model.id).messages, model)] == [
                "Hi"
            ]
        assert bodies[0]["max_tokens"] == 4096 and bodies[0]["reasoning_effort"] == "low"
        assert bodies[1]["max_tokens"] == 2048 and "reasoning_effort" not in bodies[1]
        assert bodies[2]["chat_template_kwargs"] == {"reasoning_effort": "max"}
        assert "reasoning_effort" not in bodies[2]
        assert bodies[3]["max_completion_tokens"] == 512 and "max_tokens" not in bodies[3]
    finally:
        await provider.aclose()


def test_unknown_operator_approval_requires_evidence(llm_config: Settings) -> None:
    assert chat_compatible(classify("fixture-alpha", llm_config.llm_models))
    assert not chat_compatible(
        classify(
            "fixture-unapproved",
            (LLMModel(id="fixture-unapproved", name="Unapproved", category="CHAT"),),
        )
    )
    embedding = next(model for model in REGISTRY.values() if model.category == "EMBEDDING")
    override = llm_config.llm_models[0].model_copy(update={"id": embedding.id})
    assert not chat_compatible(classify(embedding.id, (override,)))


def test_discovery_needs_no_static_model_ids(llm_config: Settings) -> None:
    settings = EnvironmentSettings(
        **(
            llm_config.model_dump()
            | {
                "llm_models": (),
                "llm_default_model": None,
            }
        )
    )
    assert settings.llm_models == ()
