import asyncio
import json
import logging
from collections.abc import AsyncIterator, Sequence

import pytest
from httpx import ASGITransport, AsyncClient

from noris_ai.core.config import EnvironmentSettings, Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.provider import ProviderMessage
from noris_ai.llm.provider_models import ProviderModel
from noris_ai.llm.schemas import ChatRequest, ConversationTitleRequest, LLMMessage, LLMModel
from noris_ai.llm.titles import TITLE_INSTRUCTION, title_source, validate_title
from noris_ai.main import create_app
from tests.fixtures.provider_catalog import provider_model

AUTH = ("fixture-user", "fixture-application-password-never-real")
PAYLOAD: dict[str, object] = {
    "conversationId": "title-chat",
    "inputMessageId": "title-input",
    "modelId": "fixture-alpha",
    "firstMessage": "Warum funktioniert Docker DNS nicht?",
}


class TitleProvider:
    def __init__(self, output: str = "Docker DNS-Probleme", failure: str | None = None) -> None:
        self.output, self.failure = output, failure
        self.calls: list[tuple[Sequence[ProviderMessage], LLMModel]] = []
        self.received, self.closed = asyncio.Event(), asyncio.Event()
        self.wait = False

    async def stream(
        self, messages: Sequence[ProviderMessage], model: LLMModel
    ) -> AsyncIterator[str]:
        self.calls.append((messages, model))
        self.received.set()
        try:
            if self.wait:
                await asyncio.Event().wait()
            if self.failure:
                raise LLMError(self.failure)
            for char in self.output:
                yield char
        finally:
            self.closed.set()

    async def discover_models(self) -> list[ProviderModel]:
        return [provider_model(value) for value in ["fixture-alpha", "fixture-beta"]]

    async def aclose(self) -> None:
        pass


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Docker DNS-Probleme", "Docker DNS-Probleme"),
        ('  "Rust vs. C++".  ', "Rust vs. C++"),
        ("„PostgreSQL vs. MariaDB“", "PostgreSQL vs. MariaDB"),
        ("Docker DNS troubleshooting", "Docker DNS troubleshooting"),
        ("Noris AI Docker-Setup", "Noris AI Docker-Setup"),
        ("Docker DNS", "Docker DNS"),
        ("\r\n Docker DNS \n", "Docker DNS"),
        ("Add MCP to Codex now", "Add MCP to Codex now"),
        ("ÖPNV & Mobilität", "ÖPNV & Mobilität"),
        ("Datenbankzugriffsrechte prüfen", "Datenbankzugriffsrechte prüfen"),
        ("A" * 37 + " BB", "A" * 37 + " BB"),
        ("A" * 38 + " BB", None),
        ("Automatisierte Chat-Titel Implementierung", "Automatische Chat-Titel"),
        ("Docker", None),
        ("eins zwei drei vier fünf sechs", None),
        ("Docker DNS...", None),
        ("Docker DNS…", None),
        ("Bitte Docker erklären", None),
        ("Kannst du Docker erklären", None),
        ("Can you explain Docker", None),
        ("Docker DNS:", None),
        ("Docker DNS;", None),
        ("Docker\tDNS", None),
        ("\tDocker DNS", None),
        ("A" * 51, None),
        ("eins zwei drei vier fünf sechs sieben", None),
        ("Docker\nErläuterung", None),
        ("Wie Docker eingerichtet wird", None),
        ("Hello Docker", None),
        ("Neue Unterhaltung", None),
        ("Neue  Unterhaltung", None),
        ("Docker 😀", None),
        ("Docker\u202eDNS", None),
        ("Docker https://example.com/private", None),
        ("Kontakt test@example.com", None),
        ("API token=synthetic-secret", None),
        ("Noris sk-synthetic-key", None),
        ("", None),
        ("<script>alert(1)</script>", None),
    ],
)
def test_title_validation(raw: str, expected: str | None) -> None:
    if expected is None:
        with pytest.raises(LLMError) as raised:
            validate_title(raw)
        assert raised.value.code == "INVALID_RESPONSE"
    else:
        assert validate_title(raw) == expected


def test_additional_request_redacts_obvious_private_data() -> None:
    message = (
        "Docker für test@example.com password=synthetic-secret "
        "Bearer synthetic-auth https://example.com/?token=synthetic "
        "sk-synthetic-key 550e8400-e29b-41d4-a716-446655440000"
    )
    assert title_source(message).startswith("Docker für [private data]")
    assert "synthetic" not in title_source(message)
    assert "example.com" not in title_source(message)
    assert title_source("Rust vs. C++ und PostgreSQL 18") == "Rust vs. C++ und PostgreSQL 18"


async def test_title_endpoint_uses_server_instruction_and_only_first_input(
    llm_config: Settings,
) -> None:
    provider = TitleProvider()
    app = create_app(llm_config, provider=provider)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=AUTH) as client,
    ):
        response = await client.post("/api/v1/llm/conversation-title", json=PAYLOAD)
        assert response.status_code == 200
        assert response.json() == {
            "conversationId": "title-chat",
            "inputMessageId": "title-input",
            "title": "Docker DNS-Probleme",
        }
        messages, model = provider.calls[0]
        assert [message.model_dump() for message in messages] == [
            {"role": "system", "content": TITLE_INSTRUCTION},
            {"role": "user", "content": PAYLOAD["firstMessage"]},
        ]
        assert model.max_output_tokens == 96
        assert llm_config.llm_models[0].max_output_tokens == 1024
        duplicate = await client.post("/api/v1/llm/conversation-title", json=PAYLOAD)
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "TITLE_ALREADY_ATTEMPTED"
        assert len(provider.calls) == 1


@pytest.mark.parametrize(
    "update,headers,status,code",
    [
        ({"firstMessage": " "}, {}, 422, "VALIDATION_ERROR"),
        ({"firstMessage": "\ud800"}, {}, 422, "VALIDATION_ERROR"),
        ({"firstMessage": "x" * 1025}, {}, 422, "VALIDATION_ERROR"),
        ({"messages": [{"role": "system", "content": "override"}]}, {}, 422, "VALIDATION_ERROR"),
        ({"system": "override"}, {}, 422, "VALIDATION_ERROR"),
        ({"modelId": "missing"}, {}, 400, "MODEL_UNAVAILABLE"),
        ({}, {"Origin": "https://evil.example"}, 403, "ORIGIN_DENIED"),
        ({}, {"Sec-Fetch-Site": "cross-site"}, 403, "ORIGIN_DENIED"),
    ],
)
async def test_title_request_rejected_before_provider(
    llm_config: Settings, update: dict[str, object], headers: dict[str, str], status: int, code: str
) -> None:
    provider = TitleProvider()
    app = create_app(llm_config, provider=provider)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=AUTH) as client,
    ):
        response = await client.post(
            "/api/v1/llm/conversation-title",
            content=json.dumps(PAYLOAD | update, ensure_ascii=True),
            headers={"Content-Type": "application/json"} | headers,
        )
        assert response.status_code == status
        assert response.json()["error"]["code"] == code
        assert not provider.calls


async def test_title_endpoint_requires_auth_and_disabled_provider_stays_off(
    llm_config: Settings,
) -> None:
    for config, status in [(llm_config, 401), (EnvironmentSettings(environment="test"), 503)]:
        provider = TitleProvider() if status == 401 else None
        app = create_app(config, provider=provider)
        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        ):
            response = await client.post("/api/v1/llm/conversation-title", json=PAYLOAD)
            assert response.status_code == status
            if provider is not None:
                assert not provider.calls


@pytest.mark.parametrize(
    "failure",
    ["RATE_LIMIT", "BUDGET_LIMIT", "PROVIDER_UNREACHABLE", "MODEL_UNAVAILABLE", "INVALID_RESPONSE"],
)
async def test_title_errors_are_diagnostic_without_content_or_retries(
    llm_config: Settings, failure: str, caplog: pytest.LogCaptureFixture
) -> None:
    provider = TitleProvider(failure=failure)
    app = create_app(llm_config, provider=provider)
    caplog.set_level(logging.INFO, logger="noris_ai.api.v1.llm")
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=AUTH) as client,
    ):
        response = await client.post("/api/v1/llm/conversation-title", json=PAYLOAD)
        assert response.json()["error"]["code"] == failure
        assert len(provider.calls) == 1
        assert failure in caplog.text
        assert str(PAYLOAD["firstMessage"]) not in caplog.text
        assert "fixture-provider-key" not in caplog.text


async def test_title_timeout_releases_shared_slot_and_prevents_retry(llm_config: Settings) -> None:
    provider = TitleProvider()
    provider.wait = True
    gateway = LLMGateway(
        llm_config.model_copy(update={"llm_title_timeout_seconds": 0.01, "llm_max_concurrent": 1}),
        provider,
    )
    request = ConversationTitleRequest.model_validate(PAYLOAD)
    with pytest.raises(LLMError) as raised:
        await gateway.conversation_title(request)
    assert raised.value.code == "TIMEOUT"
    assert provider.closed.is_set()
    with pytest.raises(LLMError) as duplicate:
        await gateway.conversation_title(request)
    assert duplicate.value.code == "TITLE_ALREADY_ATTEMPTED"
    chat = chat_request()
    await gateway.reserve(chat)
    gateway.release(chat.generationId)
    assert len(provider.calls) == 1


def chat_request() -> ChatRequest:
    return ChatRequest(
        generationId="chat-generation",
        conversationId="chat",
        inputMessageId="input",
        modelId="fixture-alpha",
        messages=[LLMMessage(role="user", content="Docker")],
        attempt=1,
    )


@pytest.mark.parametrize(
    "limit", ["llm_max_concurrent", "llm_requests_per_minute", "llm_daily_token_budget"]
)
async def test_titles_share_chat_admission_and_budget(llm_config: Settings, limit: str) -> None:
    config = llm_config.model_copy(update={limit: 1 if limit != "llm_daily_token_budget" else 2000})
    provider = TitleProvider()
    gateway = LLMGateway(config, provider)
    chat = chat_request()
    await gateway.reserve(chat)
    if limit != "llm_max_concurrent":
        gateway.release(chat.generationId)
    with pytest.raises(LLMError) as raised:
        await gateway.conversation_title(ConversationTitleRequest.model_validate(PAYLOAD))
    assert raised.value.code == (
        "BUDGET_LIMIT" if limit == "llm_daily_token_budget" else "RATE_LIMIT"
    )
    assert not provider.calls


async def test_titles_charge_budget_even_when_invalid_and_limit_output(
    llm_config: Settings,
) -> None:
    provider = TitleProvider("x" * 257)
    # Preserve the first-title allowance with the added system/context reserves;
    # the remaining budget still cannot admit another chat request.
    budget = 1500 + llm_config.llm_context_safety_tokens + llm_config.llm_system_reserved_tokens
    gateway = LLMGateway(
        llm_config.model_copy(update={"llm_max_concurrent": 1, "llm_daily_token_budget": budget}),
        provider,
    )
    with pytest.raises(LLMError) as raised:
        await gateway.conversation_title(ConversationTitleRequest.model_validate(PAYLOAD))
    assert raised.value.code == "INVALID_RESPONSE"
    assert provider.closed.is_set()
    assert provider.calls[0][1].max_output_tokens == 96
    # The released slot does not erase the failed title's shared token charge.
    with pytest.raises(LLMError) as budget:
        await gateway.reserve(chat_request())
    assert budget.value.code == "BUDGET_LIMIT"
