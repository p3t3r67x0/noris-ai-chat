import json
from collections.abc import AsyncIterator, Sequence
from typing import Literal, cast

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.provider import ProviderMessage
from noris_ai.llm.schemas import LLMModel
from noris_ai.llm.sse import SSEDecoder
from noris_ai.llm.titles import TitleInstruction


class ProviderDelta(BaseModel):
    model_config = ConfigDict(strict=True)
    content: str | None = None
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

    async def stream(
        self, messages: Sequence[ProviderMessage], model: LLMModel
    ) -> AsyncIterator[str]:
        key = self._config.llm_api_key
        base = self._config.llm_base_url
        if key is None or base is None:
            raise LLMError("LLM_DISABLED", 503)
        body: dict[str, object] = {
            "model": model.id,
            "messages": [message.model_dump() for message in messages],
            "stream": True,
            self._config.llm_token_limit_parameter: model.max_output_tokens,
        }
        if self._config.llm_reasoning_effort is not None:
            body["reasoning_effort"] = (
                "low"
                if any(isinstance(message, TitleInstruction) for message in messages)
                else self._config.llm_reasoning_effort
            )
        try:
            async with self._client.stream(
                "POST",
                base.rstrip("/") + "/chat/completions",
                headers={
                    "Authorization": "Bearer " + key.get_secret_value(),
                    "Accept": "text/event-stream",
                },
                json=body,
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
                        if len(event.choices) != 1 or finished:
                            raise LLMError("INVALID_RESPONSE")
                        choice = event.choices[0]
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
