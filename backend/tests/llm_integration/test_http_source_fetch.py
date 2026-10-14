"""Actual local TLS/HTTP over the pinned transport; no external requests."""

import asyncio
import logging
import ssl
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from noris_ai.tools.errors import ToolError
from noris_ai.tools.providers import network
from noris_ai.tools.providers.source_fetch import SourceFetchProvider, SourceFetchSettings
from tests.llm_integration.http_server import serve
from tests.unit.test_source_fetch import fetch_context


@pytest.mark.parametrize("address", ["127.0.0.1", "::1"])
@pytest.mark.parametrize("trusted_certificate", [True, False])
@pytest.mark.parametrize(
    "hostname", ["source.example.org", "wrong.example.org", "xn--bcher-kva.example.org"]
)
async def test_actual_tls_certificates_host_sni_idna_and_origin_pool_isolation(
    address: str,
    trusted_certificate: bool,
    hostname: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="httpcore.http11")
    caplog.set_level(logging.INFO, logger="httpx")
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
        "/CN=source.example.org",
        "-addext",
        "subjectAltName=DNS:source.example.org,DNS:xn--bcher-kva.example.org",
        "-keyout",
        str(key),
        "-out",
        str(certificate),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    assert await process.wait() == 0
    trusted = ssl.create_default_context()
    if trusted_certificate:
        trusted.load_verify_locations(cafile=str(certificate))
    assert trusted.check_hostname and trusted.verify_mode == ssl.CERT_REQUIRED

    def client_context(**kwargs: object) -> ssl.SSLContext:
        return trusted

    monkeypatch.setattr(ssl, "create_default_context", client_context)
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(name, "http://127.0.0.1:1")

    async def checked(request: httpx.Request, allowed: tuple[str, ...]) -> list[str]:
        assert allowed == ()
        return [address]

    # The fixture replaces DNS only with this test server's address. Separate
    # adversarial tests verify the public-address classifier without exceptions.
    monkeypatch.setattr(network, "checked_addresses", checked)
    hosts: list[str] = []
    upstream = FastAPI()

    async def page(request: Request) -> HTMLResponse:
        hosts.append(request.headers["host"])
        return HTMLResponse(
            "<article>Actual TLS text</article>",
            headers={
                "X-Private": "private-source-header",
                "Set-Cookie": "credential=private-source-cookie",
            },
        )

    upstream.add_api_route("/", page, methods=["GET"])
    async with serve(upstream, key=key, certificate=certificate, host=address) as base:
        port = cast(int, urlsplit(base).port)
        original_pin = network.pinned_request

        def pin(request: httpx.Request, resolved: str) -> httpx.Request:
            pinned = original_pin(request, resolved)
            assert pinned.extensions["sni_hostname"] == request.url.raw_host.decode("ascii")
            return httpx.Request(
                pinned.method,
                pinned.url.copy_with(port=port),
                headers=pinned.headers,
                stream=pinned.stream,
                extensions=pinned.extensions,
            )

        monkeypatch.setattr(network, "pinned_request", pin)
        async with SourceFetchProvider(SourceFetchSettings()) as provider:
            if trusted_certificate:
                # Fill all four slots with good TLS connections to the SAME IP.
                for _ in range(4):
                    await provider.fetch(
                        fetch_context(),
                        uuid4(),
                        "https://source.example.org/?token=private-source-query",
                        max_output_bytes=262_144,
                    )
            if trusted_certificate and hostname != "wrong.example.org":
                result = await provider.fetch(
                    fetch_context(), uuid4(), f"https://{hostname}/", max_output_bytes=262_144
                )
                assert result.text == "Actual TLS text"
                assert hosts[-1] == hostname
            else:
                with pytest.raises(ToolError, match="PROVIDER_ERROR"):
                    await provider.fetch(
                        fetch_context(), uuid4(), f"https://{hostname}/", max_output_bytes=262_144
                    )
    assert len(hosts) == (4 + int(hostname != "wrong.example.org") if trusted_certificate else 0)

    assert "private-source-header" not in caplog.text
    assert "private-source-cookie" not in caplog.text
    assert "private-source-query" not in caplog.text
