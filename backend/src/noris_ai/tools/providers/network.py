"""Endpoint-scoped HTTPX transport: validate DNS, then connect to the checked IP."""

import asyncio
import ipaddress
import socket

import httpx

from noris_ai.tools.errors import ToolError

_INTERNAL = tuple(
    ipaddress.ip_network(value)
    for value in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
    )
)


def permitted_address(value: str, allowed_addresses: tuple[str, ...]) -> str:
    address = ipaddress.ip_address(value)
    canonical = str(address)
    internal = any(address in network for network in _INTERNAL)
    if (
        (allowed_addresses and canonical not in allowed_addresses)
        or (not address.is_global and not (internal and canonical in allowed_addresses))
        or address.is_multicast
        or address.is_link_local
        or address.is_unspecified
        or (address.is_reserved and not internal)
        or (
            isinstance(address, ipaddress.IPv6Address)
            and (address.is_site_local or address.ipv4_mapped is not None)
        )
    ):
        raise ToolError("TOOL_FORBIDDEN")
    return canonical


class EndpointTransport(httpx.AsyncBaseTransport):
    def __init__(self, endpoint: str, allowed_addresses: tuple[str, ...]) -> None:
        self._endpoint = httpx.URL(endpoint)
        self._allowed_addresses = allowed_addresses
        self._transport = httpx.AsyncHTTPTransport(
            trust_env=False,
            verify=True,
            retries=0,
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url != self._endpoint or request.method != "POST":
            raise ToolError("TOOL_FORBIDDEN")
        host = request.url.host
        port = request.url.port or (443 if request.url.scheme == "https" else 80)
        try:
            ipaddress.ip_address(host)
        except ValueError:
            try:
                # getaddrinfo runs outside the event loop. Cancel never proceeds to HTTP.
                async with asyncio.timeout(request.extensions.get("timeout", {}).get("connect")):
                    answers = await asyncio.get_running_loop().getaddrinfo(
                        host, port, type=socket.SOCK_STREAM
                    )
            except TimeoutError:
                raise httpx.ConnectTimeout("SearXNG DNS timeout") from None
            except OSError:
                raise httpx.ConnectError("SearXNG DNS failed") from None
            addresses = sorted({str(answer[4][0]) for answer in answers})
        else:
            addresses = [host]
        if not addresses:
            raise httpx.ConnectError("SearXNG DNS failed")
        checked = [permitted_address(address, self._allowed_addresses) for address in addresses]
        if request.url.scheme != "https" and any(
            ipaddress.ip_address(address).is_global for address in checked
        ):
            raise ToolError("TOOL_FORBIDDEN")
        # No second hostname resolution, redirect or address fallback. Preserve Host
        # and TLS SNI/certificate verification for the configured hostname.
        pinned = httpx.Request(
            request.method,
            request.url.copy_with(host=checked[0]),
            headers=request.headers,
            stream=request.stream,
            extensions={**request.extensions, "sni_hostname": host},
        )
        return await self._transport.handle_async_request(pinned)

    async def aclose(self) -> None:
        await self._transport.aclose()
