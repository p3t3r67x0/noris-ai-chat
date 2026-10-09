import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from noris_ai.core.config import Settings
from noris_ai.main import create_app

from .http_server import serve

MODEL_ID = "vllm/release/gpt-oss-120b"


@pytest.mark.parametrize("scenario", ["success", "empty", "auth", "timeout", "withdraw"])
async def test_catalog_over_actual_http(llm_config: Settings, scenario: str) -> None:
    upstream = FastAPI()
    ids = [MODEL_ID]
    discovery_calls = 0

    async def discover(request: Request) -> JSONResponse | StreamingResponse:
        nonlocal discovery_calls
        discovery_calls += 1
        assert request.headers["authorization"] == "Bearer fixture-provider-key-never-real"
        if scenario == "auth":
            return JSONResponse({"error": "secret-not-forwarded"}, status_code=401)
        if scenario == "timeout":

            async def waiting() -> AsyncIterator[bytes]:
                yield b"{"
                await asyncio.Event().wait()

            return StreamingResponse(waiting(), media_type="application/json")
        return JSONResponse(
            {"data": [] if scenario == "empty" else [{"id": value} for value in ids]}
        )

    upstream.add_api_route("/v1/models", discover, methods=["GET"], response_model=None)
    async with serve(upstream) as base:
        config = llm_config.model_copy(
            update={
                "llm_base_url": base + "/v1",
                "llm_models": (),
                "llm_discovery_timeout_seconds": 0.05 if scenario == "timeout" else 10,
            }
        )
        app = create_app(config)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                auth=("fixture-user", "fixture-application-password-never-real"),
            ) as client,
        ):
            results = await asyncio.gather(*(client.get("/api/v1/llm/models") for _ in range(5)))
            assert discovery_calls == 1
            response = results[0]
            assert "secret-not-forwarded" not in response.text
            if scenario in ("auth", "timeout"):
                assert response.status_code == (502 if scenario == "auth" else 504)
                assert response.json()["error"]["code"] == (
                    "PROVIDER_AUTH_FAILED" if scenario == "auth" else "TIMEOUT"
                )
            else:
                assert response.status_code == 200
                assert len(response.json()["models"]) == (0 if scenario == "empty" else 1)
            if scenario == "withdraw":
                ids.clear()
                app.state.llm_gateway.catalog.invalidate()
                revoked = await client.post(
                    "/api/v1/llm/chat",
                    json={
                        "generationId": "withdraw",
                        "conversationId": "chat",
                        "inputMessageId": "input",
                        "modelId": MODEL_ID,
                        "messages": [{"role": "user", "content": "Hi"}],
                        "attempt": 1,
                    },
                )
                assert revoked.status_code == 400
                assert revoked.json()["error"]["code"] == "MODEL_UNAVAILABLE"
                assert discovery_calls == 2
