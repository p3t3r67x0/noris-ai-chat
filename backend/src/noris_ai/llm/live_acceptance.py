"""Opt-in local acceptance harness; never imported by the production application."""

import argparse
import asyncio
import json
import os
import secrets
import stat
from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from pathlib import Path
from time import monotonic
from typing import Any, cast

import httpx
import uvicorn
from fastapi import FastAPI
from pydantic import SecretStr, TypeAdapter, ValidationError
from pydantic_settings import SettingsConfigDict

from noris_ai.core.config import EnvironmentSettings, Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.openai_compatible import OpenAICompatibleProvider, ProviderChunk
from noris_ai.llm.provider import ProviderMessage
from noris_ai.llm.schemas import LLMModel, StreamEvent
from noris_ai.llm.sse import SSEDecoder
from noris_ai.main import create_app

MODEL_ID = "vllm/release/gpt-oss-120b"
PROMPT = "Erkläre in zwei Sätzen, was ein MCP-Server ist."


def private_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=True)
    temporary.replace(path)


class Observation:
    def __init__(self, path: Path, limit: int = 3) -> None:
        self.path, self.limit = path, limit
        self.calls: list[dict[str, Any]] = []
        if path.exists():
            saved = json.loads(path.read_text())
            if saved.get("model") != MODEL_ID or saved.get("max_output_tokens") != 256:
                raise ValueError("Incompatible acceptance state")
            calls: object = saved["calls"]
            if not isinstance(calls, list):
                raise ValueError("Invalid acceptance call count")
            self.calls = cast(list[dict[str, Any]], calls)
            if len(self.calls) > limit:
                raise ValueError("Acceptance call limit already exceeded")
        self.finished = asyncio.Event()

    def save(self) -> None:
        # Only allowlisted counters/timings; never headers, body, exceptions or secrets.
        private_json(self.path, {"model": MODEL_ID, "max_output_tokens": 256, "calls": self.calls})


class ObservedStream(httpx.AsyncByteStream):
    def __init__(
        self,
        inner: httpx.AsyncByteStream,
        call: dict[str, Any],
        observation: Observation,
        network_socket: Any,
    ) -> None:
        self.inner, self.call, self.observation, self.network_socket = (
            inner,
            call,
            observation,
            network_socket,
        )
        self.decoder = SSEDecoder()

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in self.inner:
            self.call["network_chunks"] += 1
            self.call["network_bytes"] += len(chunk)
            # Diagnose schema failures without saving any provider content or input values.
            try:
                for data in self.decoder.feed(chunk):
                    if data == "[DONE]":
                        self.call["provider_done_seen"] = True
                        continue
                    try:
                        frame = ProviderChunk.model_validate_json(data)
                        if frame.error is not None:
                            self.call["provider_error_event"] = True
                        for choice in frame.choices:
                            if choice.finish_reason is not None:
                                self.call["provider_finish_reason"] = choice.finish_reason
                    except ValidationError as error:
                        fields = {
                            "choices",
                            "delta",
                            "index",
                            "role",
                            "content",
                            "finish_reason",
                            "error",
                            "tool_calls",
                            "function_call",
                        }
                        self.call["schema_errors"] = [
                            {
                                "path": [
                                    part if isinstance(part, int) or part in fields else "other"
                                    for part in item["loc"]
                                ],
                                "type": item["type"],
                            }
                            for item in error.errors(include_input=False, include_url=False)[:10]
                        ]
            except LLMError:
                self.call["wire_sse_decode_failed"] = True
            yield chunk

    async def aclose(self) -> None:
        await self.inner.aclose()
        self.call["upstream_http_closed"] = True
        self.call["upstream_socket_closed"] = (
            self.network_socket.fileno() == -1 if self.network_socket is not None else None
        )
        self.observation.save()


class ObservedTransport(httpx.AsyncBaseTransport):
    def __init__(self, config: Settings, observation: Observation) -> None:
        self.observation = observation
        self.inner = httpx.AsyncHTTPTransport(
            trust_env=False,
            retries=0,
            limits=httpx.Limits(
                max_connections=config.llm_max_concurrent,
                max_keepalive_connections=config.llm_max_concurrent,
            ),
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        call = self.observation.calls[-1]  # Harness has one worker and one concurrent request.
        response = await self.inner.handle_async_request(request)
        call["provider_http_status"] = response.status_code
        call["provider_sse"] = response.headers.get("content-type", "").startswith(
            "text/event-stream"
        )
        network = cast(Any, response.extensions.get("network_stream"))
        sock = network.get_extra_info("socket") if network is not None else None
        response.stream = ObservedStream(
            cast(httpx.AsyncByteStream, response.stream), call, self.observation, sock
        )
        self.observation.save()
        return response

    async def aclose(self) -> None:
        await self.inner.aclose()


class ObservedProvider:
    """Observe the existing adapter, with a hard per-session paid-call ceiling."""

    def __init__(self, config: Settings, observation: Observation) -> None:
        self.observation = observation
        self.reasoning_effort = config.llm_reasoning_effort
        self.inner = OpenAICompatibleProvider(
            config, transport=ObservedTransport(config, observation)
        )

    async def stream(
        self, messages: Sequence[ProviderMessage], model: LLMModel
    ) -> AsyncIterator[str]:
        if len(self.observation.calls) >= self.observation.limit:
            raise LLMError("BUDGET_LIMIT", 429)
        started = monotonic()
        self.observation.finished.clear()
        call: dict[str, Any] = {
            "ordinal": len(self.observation.calls) + 1,
            "model": model.id,
            "text_deltas": 0,
            "text_characters": 0,
            "network_chunks": 0,
            "network_bytes": 0,
            "outcome": "streaming",
            "upstream_http_closed": False,
            "upstream_socket_closed": None,
            "reasoning_effort": self.reasoning_effort,
        }
        self.observation.calls.append(call)
        self.observation.save()
        iterator = cast(AsyncGenerator[str], self.inner.stream(messages, model))
        try:
            async for delta in iterator:
                if not call["text_deltas"]:
                    call["first_text_ms"] = round((monotonic() - started) * 1000)
                call["text_deltas"] += 1
                call["text_characters"] += len(delta)
                yield delta
            call["outcome"] = "completed"
        except (asyncio.CancelledError, GeneratorExit):
            call["outcome"] = "cancelled"
            raise
        except LLMError as error:
            call["outcome"], call["error_code"] = "failed", error.code
            raise
        finally:
            await iterator.aclose()
            call["total_ms"] = round((monotonic() - started) * 1000)
            self.observation.save()
            self.observation.finished.set()

    async def aclose(self) -> None:
        await self.inner.aclose()


def acceptance_app(config: Settings, session: Path, limit: int = 3) -> FastAPI:
    observation = Observation(session / "state.json", limit)
    observation.save()
    app = create_app(config, provider=ObservedProvider(config, observation))
    app.state.live_observation = observation
    return app


async def model_is_listed(key: str) -> bool:
    async with (
        httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client,
        client.stream(
            "GET",
            "https://ai.noris.de/v1/models",
            headers={"Authorization": "Bearer " + key, "Accept": "application/json"},
        ) as response,
    ):
        if response.status_code != 200:
            return False
        data = bytearray()
        async for chunk in response.aiter_bytes():
            data.extend(chunk)
            if len(data) > 65_536:
                return False
        payload = json.loads(data)
        return any(model.get("id") == MODEL_ID for model in payload.get("data", []))


def server(args: argparse.Namespace) -> int:
    if os.environ.get("NORIS_RUN_LIVE_LLM_SMOKE") != "1" or args.allow_paid_calls not in (3, 5):
        print('{"status":"BLOCKED","reason":"EXPLICIT_PAID_OPT_IN_REQUIRED"}')
        return 2
    key = os.environ.get("NORIS_LLM_API_KEY", "")
    if not key and args.env_file:

        class KeySource(EnvironmentSettings):
            model_config = SettingsConfigDict(env_file=Path(args.env_file).expanduser())

        source = KeySource(llm_provider="disabled").llm_api_key
        key = source.get_secret_value() if source is not None else ""
        os.environ["NORIS_LLM_API_KEY"] = key
    if not key:
        path = Path(args.key_file).expanduser()
        if stat.S_IMODE(path.stat().st_mode) & 0o077 or path.stat().st_size > 4096:
            raise ValueError("Private key file required")
        key = path.read_text().strip()
        os.environ["NORIS_LLM_API_KEY"] = key  # Only this backend process reads the key.
    if not asyncio.run(model_is_listed(key)):
        print('{"status":"BLOCKED","reason":"MODEL_NOT_LISTED_OR_AUTH_FAILED"}')
        return 2
    session = Path(args.session)
    session.mkdir(mode=0o700, parents=True, exist_ok=True)
    if session.stat().st_mode & 0o077:
        raise ValueError("Use a private session directory")
    username, password = "live-acceptance", secrets.token_urlsafe(32)
    config = EnvironmentSettings(
        environment="development",
        llm_provider="openai-compatible",
        llm_base_url="https://ai.noris.de/v1",
        llm_allowed_hosts=("ai.noris.de",),
        llm_api_key=SecretStr(key),
        llm_access_username=username,
        llm_access_password=SecretStr(password),
        llm_allowed_origins=("http://127.0.0.1:8595",),
        llm_models=(LLMModel(id=MODEL_ID, name="GPT-OSS 120B", max_output_tokens=256),),
        llm_default_model=MODEL_ID,
        llm_reasoning_effort=args.reasoning_effort,
        llm_max_concurrent=1,
        llm_requests_per_minute=3,
        llm_daily_token_budget=2500,
    )
    private_json(session / "access.json", {"username": username, "password": password})
    print(
        json.dumps(
            {
                "status": "READY",
                "model": MODEL_ID,
                "max_paid_calls": args.allow_paid_calls,
                "max_output_tokens": 256,
            }
        ),
        flush=True,
    )
    try:
        uvicorn.run(
            acceptance_app(config, session, limit=args.allow_paid_calls),
            host="127.0.0.1",
            port=8594,
            access_log=False,
            log_config=None,
            log_level="critical",
        )
    finally:
        (session / "access.json").unlink(missing_ok=True)
    return 0


async def http_probe(session: Path) -> int:
    access = json.loads((session / "access.json").read_text())
    report: dict[str, Any] = {"model": MODEL_ID, "max_output_tokens": 256}
    payload = {
        "generationId": "live-http-probe",
        "conversationId": "live-acceptance",
        "inputMessageId": "live-question",
        "modelId": MODEL_ID,
        "messages": [{"role": "user", "content": PROMPT}],
        "attempt": 1,
    }
    started = monotonic()
    text = ""
    events: list[str] = []
    sequence = 0
    adapter = TypeAdapter[StreamEvent](StreamEvent)
    async with httpx.AsyncClient(
        timeout=130,
        trust_env=False,
        auth=(access["username"], access["password"]),
    ) as client:
        anonymous = await client.get("http://127.0.0.1:8594/api/v1/llm/models", auth=None)
        report["anonymous_denied"] = anonymous.status_code == 401
        async with client.stream(
            "POST", "http://127.0.0.1:8594/api/v1/llm/chat", json=payload
        ) as response:
            report["app_http_status"] = response.status_code
            report["app_sse"] = response.headers.get("content-type", "").startswith(
                "text/event-stream"
            )
            decoder = SSEDecoder()
            async for chunk in response.aiter_bytes():
                for data in decoder.feed(chunk):
                    event = adapter.validate_json(data)
                    if event.seq != sequence + 1:
                        raise ValueError("Invalid sequence")
                    sequence = event.seq
                    events.append(event.type)
                    if event.type == "response.output_text.delta":
                        if not text:
                            report["first_text_ms"] = round((monotonic() - started) * 1000)
                        text += event.delta
                    if event.type == "response.failed":
                        report["error_code"] = event.code
            report["utf8_valid"] = not decoder.incomplete
    report.update(
        completed=bool(events and events[-1] == "response.completed"),
        text_deltas=events.count("response.output_text.delta"),
        text_characters=len(text),
        content_mentions_mcp="mcp" in text.lower(),
        total_ms=round((monotonic() - started) * 1000),
    )
    report["status"] = (
        "PASS"
        if all(
            (
                report["completed"],
                report["content_mentions_mcp"],
                report["utf8_valid"],
                report["anonymous_denied"],
            )
        )
        else "FAIL"
    )
    private_json(session / "http-result.json", report)
    print(json.dumps(report))
    return 0 if report["status"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Explicitly authorized, capped local live acceptance"
    )
    parser.add_argument("mode", choices=("server", "http"))
    parser.add_argument("--session", required=True)
    parser.add_argument("--key-file", default="~/.config/noris/api_key")
    parser.add_argument("--env-file")
    parser.add_argument("--reasoning-effort", choices=("low", "medium", "high"))
    parser.add_argument("--allow-paid-calls", type=int, default=0)
    args = parser.parse_args()
    try:
        if args.mode == "server":
            return server(args)
        if os.environ.get("NORIS_RUN_LIVE_LLM_SMOKE") != "1" or args.allow_paid_calls not in (3, 5):
            print('{"status":"BLOCKED","reason":"EXPLICIT_PAID_OPT_IN_REQUIRED"}')
            return 2
        return asyncio.run(http_probe(Path(args.session)))
    except Exception:
        # Never print exception details: configuration and HTTP errors can carry secrets.
        print('{"status":"BLOCKED","reason":"LIVE_SETUP_OR_CONNECTION_FAILED"}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
