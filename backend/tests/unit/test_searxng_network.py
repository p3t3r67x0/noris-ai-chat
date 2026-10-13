import asyncio
import socket
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import ValidationError

from noris_ai.tools.errors import ToolError
from noris_ai.tools.providers.network import EndpointTransport, permitted_address
from tests.unit.test_searxng_provider import settings


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.2", "192.168.1.2", "::1", "fd00::2"])
def test_private_exception_is_only_the_explicit_address(address: str) -> None:
    with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
        permitted_address(address, ())
    assert permitted_address(address, (address,)) == address
    with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
        permitted_address(address, ("127.0.0.2",))


@pytest.mark.parametrize(
    "address",
    [
        "169.254.169.254",
        "100.100.100.200",
        "169.254.1.2",
        "fe80::1",
        "224.0.0.1",
        "0.0.0.0",  # noqa: S104 - adversarial input, never a bind address
        "::",
        "::ffff:127.0.0.1",
        "192.0.2.1",
    ],
)
def test_special_targets_are_forbidden_even_if_allowlisted(address: str) -> None:
    with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
        permitted_address(address, (address,))
    with pytest.raises(ValidationError):
        settings(allowed_addresses=(address,))


async def test_dns_rebinding_pins_actual_connection_and_preserves_tls_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolution = AsyncMock(
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    )
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolution)
    requests: list[httpx.Request] = []

    async def transport(self: httpx.AsyncHTTPTransport, request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, stream=httpx.ByteStream(b"{}"))

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", transport)
    async with EndpointTransport("https://search.example.org/search", ()) as client:
        await client.handle_async_request(
            httpx.Request("POST", "https://search.example.org/search")
        )
        assert requests[0].url.host == "93.184.216.34"
        assert requests[0].headers["host"] == "search.example.org"
        assert requests[0].extensions["sni_hostname"] == "search.example.org"
        assert resolution.await_count == 1
        resolution.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
            await client.handle_async_request(
                httpx.Request("POST", "https://search.example.org/search")
            )
        assert len(requests) == 1


@pytest.mark.parametrize(
    "url",
    [
        "http://search.example.org/search",
        "https://other.example.org/search",
        "https://search.example.org/other",
        "https://search.example.org/search?host=evil",
    ],
)
async def test_transport_is_bound_to_exact_endpoint(url: str) -> None:
    async with EndpointTransport("https://search.example.org/search", ()) as transport:
        with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
            await transport.handle_async_request(httpx.Request("POST", url))


@pytest.mark.parametrize("operation", ["cancel", "timeout", "error", "mixed", "http"])
async def test_dns_fails_closed_and_is_cancellable(
    operation: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered = asyncio.Event()
    network = AsyncMock()
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", network)

    async def resolve(*args: object, **kwargs: object):
        entered.set()
        if operation in {"cancel", "timeout"}:
            await asyncio.Event().wait()
        if operation == "error":
            raise socket.gaierror("secret resolver details")
        addresses = ["93.184.216.34", "127.0.0.1"] if operation == "mixed" else ["93.184.216.34"]
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443)) for address in addresses
        ]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    scheme = "http" if operation == "http" else "https"
    url = f"{scheme}://search.example.org/search"
    async with EndpointTransport(url, ()) as transport:
        task = asyncio.create_task(
            transport.handle_async_request(
                httpx.Request("POST", url, extensions={"timeout": {"connect": 0.02}})
            )
        )
        await entered.wait()
        if operation == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises((ToolError, httpx.ConnectError, httpx.ConnectTimeout)) as error:
                await task
            assert "secret" not in str(error.value)
    network.assert_not_called()
