import asyncio
import socket
from unittest.mock import AsyncMock

import httpx
import pytest

from noris_ai.tools.errors import ToolError
from noris_ai.tools.providers.network import PublicSourceTransport, public_source_url


@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/",
        "https://127.0.0.1/",
        "https://127.99.0.2/",
        "https://[::1]/",
        "https://10.0.0.2/",
        "https://172.17.0.1/",
        "https://192.168.1.1/",
        "https://[fd00::1]/",
        "https://[fe80::1]/",
        "https://169.254.169.254/",
        "https://100.100.100.200/",
        "https://[::ffff:93.184.216.34]/",
        "https://[64:ff9b::5db8:d822]/",
        "https://[2002:5db8:d822::1]/",
        "https://[2001::1]/",
        "https://224.0.0.1/",
        "https://192.0.2.1/",
        "https://user:secret@source.example.org/",
        "https://@source.example.org/",
        "https://source.example.org:8080/",
        "https://source.example.org:0/",
        "http://source.example.org/",
        "file:///etc/passwd",
        "ftp://source.example.org/",
        "https://source.example.org/" + "x" * 2048,
        "https://source.example.org/\x00",
        "https://source.example.org\\@localhost/",
        "https://%6cocalhost/",
    ],
)
def test_public_source_policy_has_no_private_exception(url: str):
    with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
        public_source_url(url)


@pytest.mark.parametrize("host", ["source.example.org", "xn--bcher-kva.example.org"])
@pytest.mark.parametrize(
    "addresses",
    [
        ["93.184.216.34"],
        ["2606:4700:4700::1111"],
        ["93.184.216.34", "127.0.0.1"],
        ["93.184.216.34", "fd00::1"],
    ],
)
async def test_all_dns_answers_and_actual_ip_host_sni(
    host: str, addresses: list[str], monkeypatch: pytest.MonkeyPatch
):
    dns = AsyncMock(
        return_value=[
            (socket.AF_INET6 if ":" in a else socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 443))
            for a in addresses
        ]
    )
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", dns)
    network = AsyncMock(return_value=httpx.Response(200, stream=httpx.ByteStream(b"")))
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", network)
    async with PublicSourceTransport() as transport:
        request = httpx.Request("GET", f"https://{host}/")
        if len(addresses) == 1:
            await transport.handle_async_request(request)
            pinned = network.call_args.args[0]
            assert pinned.url.host == addresses[0]
            assert pinned.headers["host"] == host
            assert pinned.extensions["sni_hostname"] == host
            # The next attempt re-resolves. It never reuses a previously allowed DNS answer.
            dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))]
            with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
                await transport.handle_async_request(request)
            assert network.await_count == 1
        else:
            with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
                await transport.handle_async_request(request)
            network.assert_not_called()


@pytest.mark.parametrize("operation", ["cancel", "timeout", "error"])
async def test_dns_cancel_timeout_and_error_close_before_connect(
    operation: str, monkeypatch: pytest.MonkeyPatch
):
    entered = asyncio.Event()

    async def resolve(*args: object, **kwargs: object):
        entered.set()
        if operation == "error":
            raise socket.gaierror("secret")
        await asyncio.Event().wait()
        return list[object]()

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    network = AsyncMock()
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", network)
    async with PublicSourceTransport() as transport:
        task = asyncio.create_task(
            transport.handle_async_request(
                httpx.Request(
                    "GET", "https://source.example.org/", extensions={"timeout": {"connect": 0.02}}
                )
            )
        )
        await entered.wait()
        if operation == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(
                httpx.ConnectError if operation == "error" else httpx.ConnectTimeout
            ):
                await task
    network.assert_not_called()


async def test_proxy_environment_ignored_and_idna_canonicalized(monkeypatch: pytest.MonkeyPatch):
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(name, "http://127.0.0.1:9999")
    calls: list[dict[str, object]] = []
    original = httpx.AsyncHTTPTransport.__init__

    def init(self: httpx.AsyncHTTPTransport, **kwargs: object):
        calls.append(kwargs)
        original(self, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "__init__", init)
    async with PublicSourceTransport():
        pass
    assert calls[0]["trust_env"] is False and calls[0]["verify"] is True
    assert "proxy" not in calls[0] and "uds" not in calls[0]
    assert public_source_url("https://bücher.example.org/").raw_host == b"xn--bcher-kva.example.org"


@pytest.mark.parametrize("target", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "fd00::1"])
async def test_dns_redirect_checks_every_target_before_connect(
    target: str,
    monkeypatch: pytest.MonkeyPatch,
):
    from uuid import uuid4

    from noris_ai.tools.providers.source_fetch import SourceFetchProvider, SourceFetchSettings
    from tests.unit.test_source_fetch import fetch_context

    resolutions: list[str] = []

    async def resolve(host: str, port: int, **kwargs: object):
        resolutions.append(host)
        address = "93.184.216.34" if host == "source.example.org" else target
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    calls = 0

    async def network(self: httpx.AsyncHTTPTransport, request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            302, headers={"Location": "https://redirect.example.org/"}, stream=httpx.ByteStream(b"")
        )

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", network)
    async with SourceFetchProvider(SourceFetchSettings()) as p:
        with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
            await p.fetch(
                fetch_context(), uuid4(), "https://source.example.org/", max_output_bytes=262_144
            )
    assert calls == 1 and resolutions == ["source.example.org", "redirect.example.org"]


@pytest.mark.parametrize(
    "addresses, expected",
    [
        (["2a05:d014:58f:6200::258", "35.157.26.135"], "35.157.26.135"),
        (["35.157.26.135", "2a05:d014:58f:6200::258"], "35.157.26.135"),
        (["2606:4700:4700::1111", "93.184.216.34"], "93.184.216.34"),
        (["2606:4700:4700::1111"], "2606:4700:4700::1111"),
    ],
)
async def test_dual_stack_sources_prefer_validated_ipv4_and_keep_ipv6_only(
    addresses: list[str], expected: str, monkeypatch: pytest.MonkeyPatch
):
    dns = AsyncMock(
        return_value=[
            (socket.AF_INET6 if ":" in a else socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 443))
            for a in addresses
        ]
    )
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", dns)
    network = AsyncMock(return_value=httpx.Response(200, stream=httpx.ByteStream(b"")))
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", network)
    async with PublicSourceTransport() as transport:
        response = await transport.handle_async_request(
            httpx.Request("GET", "https://source.example.org/page")
        )
        await response.aclose()
    dns.assert_awaited_once_with("source.example.org", 443, type=socket.SOCK_STREAM)
    network.assert_awaited_once()
    pinned = network.call_args.args[0]
    assert pinned.url.host == expected
    assert pinned.headers["host"] == "source.example.org"
    assert pinned.extensions["sni_hostname"] == "source.example.org"


@pytest.mark.parametrize(
    "addresses",
    [
        ["35.157.26.135", "fd00::1"],
        ["fd00::1", "35.157.26.135"],
        ["10.0.0.1", "2606:4700:4700::1111"],
        ["2606:4700:4700::1111", "10.0.0.1"],
    ],
)
async def test_dual_stack_source_validates_every_family_before_connect(
    addresses: list[str], monkeypatch: pytest.MonkeyPatch
):
    dns = AsyncMock(
        return_value=[
            (socket.AF_INET6 if ":" in a else socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 443))
            for a in addresses
        ]
    )
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", dns)
    network = AsyncMock()
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", network)
    async with PublicSourceTransport() as transport:
        with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
            await transport.handle_async_request(
                httpx.Request("GET", "https://source.example.org/")
            )
    dns.assert_awaited_once()
    network.assert_not_called()


async def test_dual_stack_source_connect_failure_does_not_retry_another_address(
    monkeypatch: pytest.MonkeyPatch,
):
    dns = AsyncMock(
        return_value=[
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700:4700::1111", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ]
    )
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", dns)
    network = AsyncMock(side_effect=httpx.ConnectError("fixture connection refused"))
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", network)
    async with PublicSourceTransport() as transport:
        with pytest.raises(httpx.ConnectError):
            await transport.handle_async_request(
                httpx.Request("GET", "https://source.example.org/")
            )
    dns.assert_awaited_once()
    network.assert_awaited_once()
    assert network.call_args.args[0].url.host == "93.184.216.34"
