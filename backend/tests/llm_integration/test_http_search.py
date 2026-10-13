"""Real loopback sockets only; no live SearXNG/search engines or PostgreSQL required."""

import asyncio
import ssl
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse

from noris_ai.tools.providers.searxng import SearXNGError, SearXNGProvider, SearXNGSettings
from noris_ai.tools.schemas import SearchInput

from .http_server import serve


def config(base: str, **overrides: object) -> SearXNGSettings:
    return SearXNGSettings.model_validate(
        {
            "base_url": base,
            "allowed_hosts": ("127.0.0.1",),
            "allowed_addresses": ("127.0.0.1",),
            "config_version": "http-fixture",
            **overrides,
        }
    )


@pytest.mark.parametrize(
    "scenario",
    [
        "success",
        "empty",
        "invalid_json",
        "403",
        "429",
        "500",
        "redirect",
        "large",
    ],
)
async def test_provider_over_actual_http(scenario: str, monkeypatch: pytest.MonkeyPatch) -> None:
    upstream = FastAPI()
    calls = 0
    redirect_calls = 0
    # The real socket test proves that the adapter ignores ambient proxy configuration.
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")

    async def search(request: Request) -> Response:
        nonlocal calls
        calls += 1
        assert request.method == "POST"
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        assert parse_qs((await request.body()).decode()) == {
            "q": ["Open Data Flensburg"],
            "format": ["json"],
            "language": ["de"],
            "categories": ["general"],
            "pageno": ["1"],
            "safesearch": ["1"],
            "time_range": ["month"],
        }
        if scenario in {"403", "429", "500"}:
            return JSONResponse(
                {"error": "upstream-secret"},
                status_code=int(scenario),
                headers={"retry-after": "500"},
            )
        if scenario == "redirect":
            return RedirectResponse("/untrusted-target")
        if scenario == "invalid_json":
            return Response(b"{", media_type="application/json")
        if scenario == "large":
            return JSONResponse({"results": [], "unused": "x" * 2000})
        return JSONResponse(
            {
                "results": []
                if scenario == "empty"
                else [
                    {"title": "Open Data", "url": "https://example.org/open", "content": "Data"},
                    {"title": "Duplicate", "url": "https://example.org/open#section"},
                    {"title": "Private", "url": "http://169.254.169.254/latest/meta-data"},
                    *[
                        {"title": f"Source {i}", "url": f"https://example.org/{i}"}
                        for i in range(10)
                    ],
                ]
            }
        )

    async def redirected() -> Response:
        nonlocal redirect_calls
        redirect_calls += 1
        return JSONResponse({"results": []})

    upstream.add_api_route("/search", search, methods=["POST"])
    upstream.add_api_route("/untrusted-target", redirected, methods=["GET", "POST"])
    async with (
        serve(upstream) as base,
        SearXNGProvider(
            config(
                base,
                max_response_bytes=1024 if scenario == "large" else 1_048_576,
            )
        ) as provider,
    ):
        query = SearchInput(query="Open Data Flensburg", language="de", time_range="month")
        if scenario in {"success", "empty"}:
            result = await provider.search(query)
            assert len(result.sources) == (8 if scenario == "success" else 0)
            assert result.partial == (scenario == "success")
            assert result.config_version == "http-fixture"
        else:
            with pytest.raises(SearXNGError) as error:
                await provider.search(query)
            assert (
                error.value.reason
                == {
                    "403": "forbidden",
                    "429": "rate_limit",
                    "500": "server_error",
                    "redirect": "redirect",
                    "invalid_json": "invalid_response",
                    "large": "response_too_large",
                }[scenario]
            )
            assert "upstream-secret" not in str(error.value)
    assert calls == 1
    assert redirect_calls == 0


@pytest.mark.parametrize("operation", ["deadline", "idle_timeout", "cancel"])
async def test_deadline_idle_timeout_and_cancellation_close_actual_http_stream(
    operation: str,
) -> None:
    upstream = FastAPI()
    entered, closed = asyncio.Event(), asyncio.Event()

    async def waiting() -> AsyncIterator[bytes]:
        try:
            entered.set()
            yield b"{"
            if operation == "deadline":
                # Bytes keep arriving within the idle limit; the total deadline must still win.
                while True:
                    await asyncio.sleep(0.1)
                    yield b" "
            await asyncio.Event().wait()
        finally:
            closed.set()

    async def blocked_search() -> StreamingResponse:
        return StreamingResponse(waiting(), media_type="application/json")

    upstream.add_api_route("/search", blocked_search, methods=["POST"])
    async with (
        serve(upstream) as base,
        SearXNGProvider(
            config(
                base,
                connect_timeout_seconds=1,
                read_timeout_seconds=1 if operation in {"idle_timeout", "deadline"} else 10,
                total_timeout_seconds=1 if operation == "deadline" else 15,
            )
        ) as provider,
    ):
        task = asyncio.create_task(provider.search(SearchInput(query="test", language="en")))
        async with asyncio.timeout(5):
            await entered.wait()
        if operation == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(SearXNGError) as error:
                await task
            assert error.value.code == "TOOL_TIMEOUT"
            assert error.value.reason == "timeout"
        async with asyncio.timeout(5):
            await closed.wait()


async def test_connection_refusal_is_safe_over_actual_socket() -> None:
    # Use an ephemeral port from the local simulator, after its listener has closed.
    async with serve(FastAPI()) as base:
        pass
    async with SearXNGProvider(config(base)) as provider:
        with pytest.raises(SearXNGError) as error:
            await provider.search(SearchInput(query="test", language="en"))
    assert error.value.reason == "connection_error"
    assert error.value.code == "PROVIDER_ERROR"
    assert not isinstance(error.value, httpx.RequestError)


@pytest.mark.parametrize("matching_hostname", [True, False])
async def test_actual_tls_pinning_preserves_certificate_validation(
    matching_hostname: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    key, certificate = tmp_path / "key.pem", tmp_path / "certificate.pem"
    process = await asyncio.create_subprocess_exec(
        "openssl",
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-days",
        "1",
        "-subj",
        "/CN=search.example.org",
        "-addext",
        "subjectAltName=DNS:search.example.org",
        "-keyout",
        str(key),
        "-out",
        str(certificate),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    assert await process.wait() == 0
    trusted = ssl.create_default_context()
    trusted.load_verify_locations(cafile=str(certificate))
    assert trusted.check_hostname and trusted.verify_mode == ssl.CERT_REQUIRED
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")

    def client_context(**kwargs: object) -> ssl.SSLContext:
        return trusted

    monkeypatch.setattr(ssl, "create_default_context", client_context)
    loop = asyncio.get_running_loop()
    original = loop.getaddrinfo

    async def resolve(host: str, port: int, **kwargs: object):
        return await original("127.0.0.1", port, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(loop, "getaddrinfo", resolve)
    calls = 0
    upstream = FastAPI()

    async def search() -> JSONResponse:
        nonlocal calls
        calls += 1
        return JSONResponse({"results": []})

    upstream.add_api_route("/search", search, methods=["POST"])
    host = "search.example.org" if matching_hostname else "wrong.example.org"
    async with (
        serve(upstream, key=key, certificate=certificate) as base,
        SearXNGProvider(config(base.replace("127.0.0.1", host), allowed_hosts=(host,))) as provider,
    ):
        if matching_hostname:
            result = await provider.search(SearchInput(query="TLS", language="en"))
            assert result.sources == []
        else:
            with pytest.raises(SearXNGError, match="PROVIDER_ERROR"):
                await provider.search(SearchInput(query="TLS", language="en"))
    assert calls == int(matching_hostname)
