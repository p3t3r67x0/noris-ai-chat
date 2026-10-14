"""Actual OpenAI-compatible HTTP/SSE for GPT-OSS/DeepSeek, no live model calls."""

import asyncio
import json
from collections.abc import AsyncIterator
from time import perf_counter
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.openai_compatible import OpenAICompatibleProvider
from noris_ai.llm.schemas import (
    CompletedEvent,
    DeltaEvent,
    FailedEvent,
    IncompleteEvent,
    LLMMessage,
    PersistedChatRequest,
    StartedEvent,
)
from noris_ai.research.grounding import GroundingContextBuilder
from tests.fixtures.provider_catalog import provider_data
from tests.unit.test_research import fetched

from .http_server import serve

MODELS = ["vllm/release/gpt-oss-120b", "vllm/qsu/deepseek-v41-flash"]


@pytest.mark.parametrize("model_id", MODELS)
@pytest.mark.parametrize("scenario", ["normal", "research", "stop", "overflow", "provider_error"])
async def test_model_grounding_stream_stop_limits_and_errors(
    llm_config: Settings,
    model_id: str,
    scenario: str,
):
    upstream = FastAPI()
    captured: list[dict[str, object]] = []
    received_at: list[float] = []
    entered, closed = asyncio.Event(), asyncio.Event()

    async def models() -> dict[str, object]:
        return {"data": [provider_data(model_id)]}

    async def completion(request: Request) -> StreamingResponse | JSONResponse:
        captured.append(await request.json())
        received_at.append(perf_counter())
        entered.set()
        if scenario == "provider_error":
            return JSONResponse({"error": "fixture-private-upstream"}, status_code=503)

        async def chunks() -> AsyncIterator[bytes]:
            try:
                yield b": keepalive\n\n"
                if scenario == "stop":
                    await asyncio.Event().wait()
                for fragment in ["Aktuelle ", "QGIS-Informationen [[R1]]."]:
                    yield (
                        "data: "
                        + json.dumps(
                            {
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "content": fragment,
                                            "reasoning_content": "private reasoning",
                                        },
                                        "finish_reason": None,
                                    }
                                ]
                            }
                        )
                        + "\n\n"
                    ).encode()
                yield b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
                yield b"data: [DONE]\n\n"
            finally:
                closed.set()

        return StreamingResponse(chunks(), media_type="text/event-stream")

    upstream.add_api_route("/v1/models", models)
    upstream.add_api_route(
        "/v1/chat/completions", completion, methods=["POST"], response_model=None
    )
    async with serve(upstream) as base:
        policy_model = llm_config.llm_models[0].model_copy(update={"id": model_id})
        config = llm_config.model_copy(
            update={"llm_base_url": base + "/v1", "llm_models": (policy_model,)}
        )
        provider = OpenAICompatibleProvider(config)
        gateway = LLMGateway(config, provider)
        request = PersistedChatRequest(
            generationId=str(uuid4()),
            conversationId=str(uuid4()),
            inputMessageId=str(uuid4()),
            modelId=model_id,
            attempt=1,
            messages=[LLMMessage(role="user", content="Latest QGIS")],
        )
        started = perf_counter()
        try:
            model, capacity = await gateway.research_capacity(request)
            if scenario == "overflow":
                with pytest.raises(LLMError, match="Kontextlimit"):
                    await gateway.reserve(request, input_token_reserve=model.context_window)
                assert not captured
                return
            if scenario != "normal":
                await gateway.reserve(request, input_token_reserve=capacity)
                request = (
                    GroundingContextBuilder(gateway)
                    .build(request, model, capacity, [fetched()])
                    .request
                )
            else:
                await gateway.reserve(request)
            iterator = gateway.events(request)
            if scenario == "stop":
                assert (await anext(iterator)).type == "response.started"  # type: ignore[union-attr]
                task = asyncio.create_task(anext(iterator))
                await asyncio.wait_for(entered.wait(), 2)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                await iterator.aclose()
                await asyncio.wait_for(closed.wait(), 2)
            else:
                events: list[
                    StartedEvent
                    | DeltaEvent
                    | CompletedEvent
                    | IncompleteEvent
                    | FailedEvent
                    | None
                ] = []
                first_token: float | None = None
                async for event in iterator:
                    events.append(event)
                    if event and event.type == "response.output_text.delta" and first_token is None:
                        first_token = perf_counter()
                if scenario == "provider_error":
                    assert any(e and e.type == "response.failed" for e in events)
                    assert "fixture-private-upstream" not in str(events)
                else:
                    deltas = [
                        e.delta for e in events if e and e.type == "response.output_text.delta"
                    ]
                    assert len(deltas) >= 2
                    assert "private reasoning" not in "".join(deltas)
                    assert any(e and e.type == "response.completed" for e in events)
                    assert first_token is not None
                    print(
                        f"llm_start_ms={(received_at[0] - started) * 1000:.1f} "
                        f"first_token_ms={(first_token - started) * 1000:.1f}"
                    )
            assert len(captured) == 1 and captured[0]["model"] == model_id
            assert "tools" not in captured[0] and "tool_choice" not in captured[0]
            messages = str(captured[0]["messages"])
            assert ("EXTERNAL_SOURCE_CONTENT" in messages) == (scenario != "normal")
            print(f"{model_id} {scenario} llm_ms={(perf_counter() - started) * 1000:.1f}")
        finally:
            await gateway.abandon(request.generationId)
            await provider.aclose()
