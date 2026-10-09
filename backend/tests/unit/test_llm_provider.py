import asyncio
import json
from collections.abc import AsyncIterator

import httpx
import pytest

from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.openai_compatible import OpenAICompatibleProvider
from noris_ai.llm.schemas import LLMMessage
from noris_ai.llm.sse import SSEDecoder


def event(content: str = "", finish: str | None = None) -> bytes:
    value = {"choices": [{"index": 0, "delta": {"content": content}, "finish_reason": finish}]}
    return ("data: " + json.dumps(value, ensure_ascii=False) + "\r\n\r\n").encode()


class Fragments(httpx.AsyncByteStream):
    def __init__(self, data: bytes, size: int = 1, wait: bool = False) -> None:
        self.data, self.size, self.wait = data, size, wait
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for offset in range(0, len(self.data), self.size):
            yield self.data[offset : offset + self.size]
        if self.wait:
            await asyncio.Event().wait()

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.parametrize("size", [1, 2, 7, 8192])
async def test_provider_handles_utf8_and_network_boundaries(
    llm_config: Settings, llm_messages: list[LLMMessage], size: int
) -> None:
    stream = Fragments(event("Grüße 🌍") + event(finish="stop") + b"data: [DONE]\r\n\r\n", size)
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, stream=stream)

    provider = OpenAICompatibleProvider(llm_config, transport=httpx.MockTransport(handler))
    try:
        result = [delta async for delta in provider.stream(llm_messages, llm_config.llm_models[0])]
    finally:
        await provider.aclose()
    assert result == ["Grüße 🌍"]
    assert stream.closed
    assert len(captured) == 1
    assert str(captured[0].url) == "http://127.0.0.1:9999/v1/chat/completions"
    assert captured[0].headers["authorization"] == "Bearer fixture-provider-key-never-real"
    assert json.loads(captured[0].content) == {
        "model": "fixture-alpha",
        "messages": [{"role": "user", "content": "Hallo 🌍"}],
        "stream": True,
        "max_tokens": 1024,
    }


@pytest.mark.parametrize("terminal_finish", [True, False])
async def test_noris_intermediate_chunks_may_omit_finish_reason(
    llm_config: Settings, llm_messages: list[LLMMessage], terminal_finish: bool
) -> None:
    first = b'data: {"choices":[{"index":0,"delta":{"content":"MCP"}}]}\n\n'
    data = first + (event(finish="stop") if terminal_finish else b"") + b"data: [DONE]\n\n"
    provider = OpenAICompatibleProvider(
        llm_config,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, headers={"Content-Type": "text/event-stream"}, content=data
            )
        ),
    )
    try:
        if terminal_finish:
            assert [
                delta async for delta in provider.stream(llm_messages, llm_config.llm_models[0])
            ] == ["MCP"]
        else:
            with pytest.raises(LLMError) as caught:
                _ = [
                    delta async for delta in provider.stream(llm_messages, llm_config.llm_models[0])
                ]
            assert caught.value.code == "INVALID_RESPONSE"
    finally:
        await provider.aclose()


async def test_server_reasoning_hint_preserves_the_output_token_cap(
    llm_config: Settings, llm_messages: list[LLMMessage]
) -> None:
    captured: list[httpx.Request] = []

    def reply(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=event("MCP") + event(finish="stop") + b"data: [DONE]\n\n",
        )

    config = llm_config.model_copy(update={"llm_reasoning_effort": "low"})
    provider = OpenAICompatibleProvider(config, transport=httpx.MockTransport(reply))
    try:
        assert [
            text
            async for text in provider.stream(
                llm_messages, config.llm_models[0].model_copy(update={"reasoning_effort": "low"})
            )
        ] == ["MCP"]
        body = json.loads(captured[0].content)
        assert body["reasoning_effort"] == "low"
        assert body["max_tokens"] == config.llm_models[0].max_output_tokens
        assert body["messages"] == [{"role": "user", "content": "Hallo 🌍"}]
    finally:
        await provider.aclose()


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "PROVIDER_AUTH_FAILED"),
        (403, "PROVIDER_AUTH_FAILED"),
        (429, "RATE_LIMIT"),
        (404, "MODEL_UNAVAILABLE"),
        (500, "PROVIDER_ERROR"),
        (307, "PROVIDER_ERROR"),
    ],
)
async def test_status_mapping_never_echoes_upstream_secrets(
    llm_config: Settings, llm_messages: list[LLMMessage], status: int, code: str
) -> None:
    provider = OpenAICompatibleProvider(
        llm_config,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                status, text="private provider secret", headers={"Location": "https://evil.example"}
            )
        ),
    )
    try:
        with pytest.raises(LLMError) as caught:
            _ = [delta async for delta in provider.stream(llm_messages, llm_config.llm_models[0])]
        assert caught.value.code == code
        assert "private" not in str(caught.value)
    finally:
        await provider.aclose()


@pytest.mark.parametrize(
    "data,code",
    [
        (b"data: invalid-json\n\n", "INVALID_RESPONSE"),
        (
            b'data: {"choices": [{"index": 0, "delta": {"content": 9}, '
            b'"finish_reason": null}]}\n\n',
            "INVALID_RESPONSE",
        ),
        (event("partial"), "STREAM_INTERRUPTED"),
        (event("partial") + event(finish="stop"), "STREAM_INTERRUPTED"),
        (event(finish="stop") + b"data: [DONE]\n\n", "INVALID_RESPONSE"),
        (event("partial", "length"), "OUTPUT_LIMIT"),
        (event(finish="content_filter"), "CONTENT_FILTERED"),
        (event("🌍" * 16001), "OUTPUT_LIMIT"),
        (b"data: \xff\n\n", "INVALID_RESPONSE"),
    ],
)
async def test_invalid_empty_and_truncated_responses(
    llm_config: Settings, llm_messages: list[LLMMessage], data: bytes, code: str
) -> None:
    stream = Fragments(data, 128)
    provider = OpenAICompatibleProvider(
        llm_config.model_copy(update={"llm_max_response_chars": 32_000}),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, headers={"Content-Type": "text/event-stream"}, stream=stream
            )
        ),
    )
    try:
        with pytest.raises(LLMError) as caught:
            _ = [delta async for delta in provider.stream(llm_messages, llm_config.llm_models[0])]
        assert caught.value.code == code
        assert stream.closed
    finally:
        await provider.aclose()


@pytest.mark.parametrize(
    "cause,code",
    [
        (httpx.ConnectError("private-url"), "PROVIDER_UNREACHABLE"),
        (httpx.ReadTimeout("private-url"), "TIMEOUT"),
        (httpx.RemoteProtocolError("private-url"), "STREAM_INTERRUPTED"),
    ],
)
async def test_network_errors_are_sanitized(
    llm_config: Settings, llm_messages: list[LLMMessage], cause: httpx.HTTPError, code: str
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise cause

    provider = OpenAICompatibleProvider(llm_config, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(LLMError) as caught:
            _ = [delta async for delta in provider.stream(llm_messages, llm_config.llm_models[0])]
        assert caught.value.code == code
        assert "private" not in str(caught.value)
    finally:
        await provider.aclose()


async def test_cancellation_closes_upstream_before_any_delta(
    llm_config: Settings, llm_messages: list[LLMMessage]
) -> None:
    stream = Fragments(b"", wait=True)
    opened = asyncio.Event()

    def handler(_: httpx.Request) -> httpx.Response:
        opened.set()
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, stream=stream)

    provider = OpenAICompatibleProvider(llm_config, transport=httpx.MockTransport(handler))
    iterator = provider.stream(llm_messages, llm_config.llm_models[0])
    task = asyncio.ensure_future(anext(iterator))
    await opened.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stream.closed
    await provider.aclose()


def test_sse_comments_multiline_and_bounded_buffers() -> None:
    decoder = SSEDecoder(32)
    assert decoder.feed(b": comment\ndata: first\ndata: second\n\n") == ["first\nsecond"]
    with pytest.raises(LLMError):
        decoder.feed(b"x" * 33)


@pytest.mark.parametrize("separator", [b"\r", b"\r\n", b"\n"])
def test_sse_bom_and_complete_final_event_at_every_byte_boundary(separator: bytes) -> None:
    decoder = SSEDecoder()
    data = b"\xef\xbb\xbfdata: first" + separator * 2 + b"data: [DONE]" + separator * 2
    frames: list[str] = []
    for value in data:
        frames.extend(decoder.feed(bytes([value])))
    assert frames == ["first", "[DONE]"]
    assert not decoder.incomplete
