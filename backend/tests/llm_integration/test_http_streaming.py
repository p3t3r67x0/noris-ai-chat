import asyncio
import json
import socket
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from noris_ai.core.config import Settings
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.live_acceptance import Observation, acceptance_app
from noris_ai.llm.schemas import ChatRequest
from noris_ai.main import create_app


@asynccontextmanager
async def serve(app: FastAPI) -> AsyncGenerator[str]:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.setblocking(False)
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False, ws="none"))
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(5):
            while not server.started:
                if task.done():
                    await task
                await asyncio.sleep(0.01)
        yield f"http://127.0.0.1:{listener.getsockname()[1]}"
    finally:
        server.should_exit = True
        async with asyncio.timeout(5):
            await task
        listener.close()


AUTH = ("fixture-user", "fixture-application-password-never-real")
PAYLOAD: dict[str, object] = {
    "generationId": "http-generation",
    "conversationId": "http-conversation",
    "inputMessageId": "http-input",
    "modelId": "fixture-alpha",
    "attempt": 1,
    "messages": [{"role": "user", "content": "Hallo"}],
}


@pytest.mark.parametrize("scenario", ["success", "rate", "timeout", "invalid", "disconnect"])
async def test_actual_gateway_and_provider_http(llm_config: Settings, scenario: str) -> None:
    upstream = FastAPI()
    closed = asyncio.Event()
    captured: list[dict[str, object]] = []
    received = asyncio.Event()

    async def completion(request: Request) -> StreamingResponse | JSONResponse:
        assert request.headers["authorization"] == "Bearer fixture-provider-key-never-real"
        captured.append(await request.json())
        received.set()
        if scenario == "rate":
            return JSONResponse({"error": {"message": "secret-upstream-info"}}, status_code=429)

        async def chunks() -> AsyncIterator[bytes]:
            try:
                if scenario in ("timeout", "disconnect"):
                    yield b": waiting\n\n"
                    await asyncio.Event().wait()
                if scenario == "invalid":
                    yield b"data: invalid-json\n\n"
                    return
                for content, finish in [("Grüße 🌍", None), ("", "stop")]:
                    data = (
                        "data: "
                        + json.dumps(
                            {
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {"content": content},
                                        "finish_reason": finish,
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                        + "\r\n\r\n"
                    ).encode()
                    for byte in data:
                        yield bytes([byte])
                        await asyncio.sleep(0)
                yield b"data: [DONE]\n\n"
            finally:
                closed.set()

        return StreamingResponse(chunks(), media_type="text/event-stream")

    upstream.add_api_route(
        "/v1/chat/completions", completion, methods=["POST"], response_model=None
    )
    async with serve(upstream) as base:
        config = llm_config.model_copy(
            update={
                "llm_base_url": base + "/v1",
                "llm_read_timeout_seconds": 0.1 if scenario == "timeout" else 5.0,
            }
        )
        gateway = create_app(config)
        async with (
            serve(gateway) as application,
            httpx.AsyncClient(base_url=application, auth=AUTH, timeout=3) as client,
        ):
            async with client.stream("POST", "/api/v1/llm/chat", json=PAYLOAD) as response:
                assert response.status_code == 200
                if scenario == "disconnect":
                    async for line in response.aiter_lines():
                        if "response.started" in line:
                            break
                    async with asyncio.timeout(2):
                        await received.wait()
                else:
                    body = (await response.aread()).decode()
                    if scenario == "success":
                        assert "Grüße 🌍" in body and "response.completed" in body
                    else:
                        code = {
                            "rate": "RATE_LIMIT",
                            "timeout": "TIMEOUT",
                            "invalid": "INVALID_RESPONSE",
                        }[scenario]
                        assert code in body and "response.completed" not in body
                        assert "secret-upstream-info" not in body
            if scenario != "rate":
                async with asyncio.timeout(2):
                    await closed.wait()
            assert captured[0]["model"] == "fixture-alpha"
            assert captured[0]["messages"] == PAYLOAD["messages"]


async def test_live_observer_confirms_socket_closure_without_recording_secrets(
    llm_config: Settings, tmp_path: Path
) -> None:
    upstream = FastAPI()
    arrived, disconnected = asyncio.Event(), asyncio.Event()

    async def completion() -> StreamingResponse:
        async def chunks() -> AsyncIterator[bytes]:
            try:
                arrived.set()
                yield b": waiting\n\n"
                await asyncio.Event().wait()
            finally:
                disconnected.set()

        return StreamingResponse(chunks(), media_type="text/event-stream")

    upstream.add_api_route("/v1/chat/completions", completion, methods=["POST"])
    async with serve(upstream) as base:
        config = llm_config.model_copy(
            update={"llm_base_url": base + "/v1", "llm_max_concurrent": 1}
        )
        app = acceptance_app(config, tmp_path)
        observation = cast(Observation, app.state.live_observation)
        async with serve(app) as application:
            async with (
                httpx.AsyncClient(base_url=application, auth=AUTH) as client,
                client.stream("POST", "/api/v1/llm/chat", json=PAYLOAD) as response,
            ):
                async for line in response.aiter_lines():
                    if "response.started" in line:
                        break
                async with asyncio.timeout(2):
                    await arrived.wait()
            async with asyncio.timeout(2):
                await disconnected.wait()
                await observation.finished.wait()
            call = json.loads((tmp_path / "state.json").read_text())["calls"][0]
            assert call["upstream_http_closed"] is True
            assert call["upstream_socket_closed"] is True
            assert "fixture-provider-key" not in (tmp_path / "state.json").read_text()


@pytest.mark.parametrize("scenario", ["success", "timeout", "disconnect"])
async def test_title_uses_existing_http_provider_and_closes_socket(
    llm_config: Settings, scenario: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    upstream = FastAPI()
    received, closed = asyncio.Event(), asyncio.Event()
    captured: list[dict[str, object]] = []

    async def completion(request: Request) -> StreamingResponse:
        captured.append(await request.json())
        received.set()

        async def chunks() -> AsyncIterator[bytes]:
            try:
                if scenario != "success":
                    yield b": waiting\n\n"
                    await asyncio.Event().wait()
                yield (
                    b'data: {"choices":[{"index":0,"delta":{"content":"Rust vs. C++"},'
                    b'"finish_reason":null}]}\n\n'
                )
                yield b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
                yield b"data: [DONE]\n\n"
            finally:
                closed.set()

        return StreamingResponse(chunks(), media_type="text/event-stream")

    upstream.add_api_route("/v1/chat/completions", completion, methods=["POST"])
    async with serve(upstream) as base:
        config = llm_config.model_copy(
            update={
                "llm_base_url": base + "/v1",
                "llm_max_concurrent": 1,
                "llm_title_timeout_seconds": 0.1 if scenario == "timeout" else 5.0,
                "llm_reasoning_effort": "medium",
            }
        )
        app = create_app(config)
        async with (
            serve(app) as application,
            httpx.AsyncClient(base_url=application, auth=AUTH, timeout=3) as client,
        ):
            gateway = cast(LLMGateway, app.state.llm_gateway)
            released = asyncio.Event()
            original_release = gateway.release

            def observed_release(generation_id: str) -> None:
                original_release(generation_id)
                released.set()

            monkeypatch.setattr(gateway, "release", observed_release)
            payload = {
                "conversationId": "http-title",
                "inputMessageId": "http-input",
                "modelId": "fixture-alpha",
                "firstMessage": "Welche Vorteile bietet Rust gegenüber C++?",
            }
            task = asyncio.create_task(client.post("/api/v1/llm/conversation-title", json=payload))
            async with asyncio.timeout(2):
                await received.wait()
            if scenario == "disconnect":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                response = await task
                if scenario == "success":
                    assert response.status_code == 200
                    assert response.json()["title"] == "Rust vs. C++"
                else:
                    assert response.status_code == 504
                    assert response.json()["error"]["code"] == "TIMEOUT"
            async with asyncio.timeout(2):
                await closed.wait()
                await released.wait()
            chat = ChatRequest.model_validate(PAYLOAD)
            gateway.reserve(chat)
            gateway.release(chat.generationId)
            assert len(captured) == 1
            messages = cast(list[dict[str, str]], captured[0]["messages"])
            assert [message["role"] for message in messages] == ["system", "user"]
            assert messages[1]["content"] == payload["firstMessage"]
            assert "untrusted" in messages[0]["content"]
            assert captured[0]["max_tokens"] == 96
            assert captured[0]["reasoning_effort"] == "low"
