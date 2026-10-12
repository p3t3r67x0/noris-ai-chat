import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from decimal import Decimal
from typing import Literal, cast

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.provider import ProviderMessage, provider_payload
from noris_ai.llm.provider_models import ProviderModel, ProviderModels
from noris_ai.llm.reasoning import preference_mapping
from noris_ai.llm.schemas import LLMModel
from noris_ai.llm.sse import SSEDecoder
from noris_ai.llm.titles import TitleInstruction
from noris_ai.llm.vision import VisionMessage, supports_images


class ProviderDelta(BaseModel):
    model_config = ConfigDict(strict=True)
    content: str | None = None
    reasoning_content: str | None = None
    reasoning: str | None = None
    role: Literal["assistant"] | None = None
    tool_calls: list[object] | None = None
    function_call: dict[str, object] | None = None


class ProviderChoice(BaseModel):
    model_config = ConfigDict(strict=True)
    index: Literal[0]
    delta: ProviderDelta
    # Noris omits this field on intermediate chunks. A terminal finish is still mandatory.
    finish_reason: (
        Literal["stop", "length", "content_filter", "tool_calls", "function_call"] | None
    ) = None


class ProviderChunk(BaseModel):
    model_config = ConfigDict(strict=True)
    choices: list[ProviderChoice]
    error: object | None = None
    usage: object | None = None


class OpenAICompatibleProvider:
    def __init__(
        self, config: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                config.llm_read_timeout_seconds,
                connect=config.llm_connect_timeout_seconds,
                write=config.llm_connect_timeout_seconds,
                pool=config.llm_connect_timeout_seconds,
            ),
            limits=httpx.Limits(
                max_connections=config.llm_max_concurrent,
                max_keepalive_connections=config.llm_max_concurrent,
            ),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def discover_models(self) -> list[ProviderModel]:
        key, base = self._config.llm_api_key, self._config.llm_base_url
        if key is None or base is None:
            raise LLMError("LLM_DISABLED", 503)
        try:
            async with asyncio.timeout(self._config.llm_discovery_timeout_seconds):
                async with self._client.stream(
                    "GET",
                    base.rstrip("/") + "/models",
                    headers={
                        "Authorization": "Bearer " + key.get_secret_value(),
                        "Accept": "application/json",
                    },
                ) as response:
                    self._validate_status(response.status_code)
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > self._config.llm_max_upstream_bytes:
                            raise LLMError("INVALID_RESPONSE")
                    try:
                        payload = ProviderModels.model_validate(
                            json.loads(data, parse_float=Decimal)
                        )
                    except ValidationError:
                        raise LLMError("INVALID_RESPONSE") from None
                    models: dict[str, ProviderModel] = {}
                    duplicates: set[str] = set()
                    seen: set[str] = set()
                    for item in payload.data:
                        candidate = (
                            cast(dict[str, object], item).get("id")
                            if isinstance(item, dict)
                            else None
                        )
                        if isinstance(candidate, str):
                            if candidate in seen:
                                duplicates.add(candidate)
                            seen.add(candidate)
                        try:
                            model = ProviderModel.model_validate(item)
                        except ValidationError:
                            continue  # Malformed entries never authorize generation.
                        if model.id in models:
                            duplicates.add(model.id)
                        models[model.id] = model
                    # Conflicting duplicate IDs have no reliable contract.
                    return [model for key, model in models.items() if key not in duplicates]
        except (TimeoutError, httpx.TimeoutException):
            raise LLMError("TIMEOUT", 504) from None
        except httpx.HTTPError:
            raise LLMError("PROVIDER_UNREACHABLE", 503) from None
        except (ValueError, UnicodeError):
            raise LLMError("INVALID_RESPONSE") from None

    async def stream(
        self, messages: Sequence[ProviderMessage], model: LLMModel
    ) -> AsyncIterator[str]:
        key = self._config.llm_api_key
        base = self._config.llm_base_url
        if key is None or base is None:
            raise LLMError("LLM_DISABLED", 503)
        has_images = any(isinstance(message, VisionMessage) for message in messages)
        if has_images and not supports_images(model):
            raise LLMError("MODEL_UNAVAILABLE", 400)
        body: dict[str, object] = {
            "model": model.id,
            "messages": [provider_payload(message) for message in messages],
            "stream": True,
        }
        if model.token_limit_parameter is None:
            raise LLMError("MODEL_UNAVAILABLE", 400)
        body[model.token_limit_parameter] = model.max_output_tokens
        effort = model.reasoning_effort
        supported_efforts = preference_mapping(model).values()
        if any(isinstance(message, TitleInstruction) for message in messages) and (
            "low" in supported_efforts
        ):
            effort = "low"
        if effort is not None and effort in supported_efforts:
            if model.reasoning_parameter == "chat_template_kwargs":
                body["chat_template_kwargs"] = {"reasoning_effort": effort}
            else:
                body["reasoning_effort"] = effort
        if has_images and len(json.dumps(body, ensure_ascii=False).encode("utf-8")) > (
            self._config.llm_max_request_bytes
        ):
            raise LLMError("REQUEST_TOO_LARGE", 413)
        try:
            async with self._client.stream(
                "POST",
                base.rstrip("/") + "/chat/completions",
                headers={
                    "Authorization": "Bearer " + key.get_secret_value(),
                    "Accept": "text/event-stream",
                },
                json=body,
                timeout=httpx.Timeout(
                    min(model.timeout_policy.read_seconds, self._config.llm_read_timeout_seconds),
                    connect=self._config.llm_connect_timeout_seconds,
                ),
            ) as response:
                await self._validate_response(response)
                if (
                    response.headers.get("content-type", "").split(";", 1)[0].strip()
                    != "text/event-stream"
                ):
                    raise LLMError("INVALID_RESPONSE")
                decoder = SSEDecoder()
                received = 0
                text_length = 0
                finished = False
                async for chunk in response.aiter_bytes():
                    received += len(chunk)
                    if received > self._config.llm_max_upstream_bytes:
                        raise LLMError("STREAM_SIZE_LIMIT")
                    for data in decoder.feed(chunk):
                        if data == "[DONE]":
                            if not finished or not text_length:
                                raise LLMError("INVALID_RESPONSE")
                            return
                        try:
                            event = ProviderChunk.model_validate_json(data)
                        except ValidationError:
                            raise LLMError("INVALID_RESPONSE") from None
                        if event.error is not None:
                            raise LLMError("PROVIDER_ERROR")
                        if not event.choices:
                            continue  # Optional usage-only metadata.
                        if len(event.choices) != 1:
                            raise LLMError("INVALID_RESPONSE")
                        choice = event.choices[0]
                        if finished:
                            # Noris may retain an empty index-0 choice in the usage trailer.
                            # Accept metadata only; new output or another finish is invalid.
                            if (
                                isinstance(event.usage, dict)
                                and choice.finish_reason is None
                                and not any(choice.delta.model_dump().values())
                            ):
                                continue
                            raise LLMError("INVALID_RESPONSE")
                        if choice.delta.tool_calls or choice.delta.function_call:
                            raise LLMError("INVALID_RESPONSE")
                        delta = choice.delta.content
                        if delta:
                            previous_length = text_length
                            text_length += len(delta.encode("utf-16-le")) // 2
                            if text_length > self._config.llm_max_response_chars:
                                available = self._config.llm_max_response_chars - previous_length
                                prefix = delta.encode("utf-16-le")[: available * 2].decode(
                                    "utf-16-le", errors="ignore"
                                )
                                if prefix:
                                    yield prefix
                                raise LLMError("RESPONSE_SIZE_LIMIT")
                            yield delta
                        if choice.finish_reason == "length":
                            raise LLMError("OUTPUT_LIMIT")
                        if choice.finish_reason == "content_filter":
                            raise LLMError("CONTENT_FILTERED")
                        if choice.finish_reason in ("tool_calls", "function_call"):
                            raise LLMError("INVALID_RESPONSE")
                        if choice.finish_reason == "stop":
                            finished = True
                raise LLMError("STREAM_INTERRUPTED")
        except httpx.TimeoutException:
            raise LLMError("TIMEOUT", 504) from None
        except httpx.ConnectError:
            raise LLMError("PROVIDER_UNREACHABLE", 503) from None
        except httpx.HTTPError:
            raise LLMError("STREAM_INTERRUPTED") from None
        except (UnicodeError, ValueError):
            raise LLMError("INVALID_RESPONSE") from None

    @classmethod
    async def _validate_response(cls, response: httpx.Response) -> None:
        if response.status_code in (400, 413):
            # Read a bounded error envelope only to recognize fixed context codes.
            # Never expose provider messages, request echoes, URLs or exception text.
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > 4096:
                    break
                body.extend(chunk)
            try:
                payload = json.loads(body)
                error = (
                    cast(dict[str, object], payload).get("error")
                    if isinstance(payload, dict)
                    else None
                )
                if isinstance(error, dict) and any(
                    cast(dict[str, object], error).get(field) == "context_length_exceeded"
                    for field in ("code", "type")
                ):
                    raise LLMError("CONTEXT_LIMIT", 413)
            except (ValueError, UnicodeError):
                pass
        cls._validate_status(response.status_code)

    @staticmethod
    def _validate_status(status: int) -> None:
        if status in (401, 403):
            raise LLMError("PROVIDER_AUTH_FAILED")
        if status == 429:
            raise LLMError("RATE_LIMIT", 429)
        if status == 404:
            raise LLMError("MODEL_UNAVAILABLE", 400)
        if status != 200:
            raise LLMError("PROVIDER_ERROR")
