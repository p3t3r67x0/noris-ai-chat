"""Endpoint-scoped HTTPX transport: validate DNS, then connect to the checked IP."""

import asyncio
import ipaddress
import socket
import unicodedata
from collections.abc import AsyncIterator
from dataclasses import dataclass
from urllib.parse import urlsplit

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
_IPV6_UNICAST = ipaddress.ip_network("2000::/3")
_TRANSITION = tuple(ipaddress.ip_network(value) for value in ("2001::/23", "2002::/16"))
_SPECIAL_V4 = tuple(
    ipaddress.ip_network(value)
    for value in (
        "192.0.0.0/24",
        "192.88.99.0/24",
        "168.63.129.16/32",
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
        or any(address in network for network in _SPECIAL_V4)
        or (address.is_reserved and not internal)
        or (
            isinstance(address, ipaddress.IPv6Address)
            and (
                address.is_site_local
                or address.ipv4_mapped is not None
                or (not internal and address not in _IPV6_UNICAST)
                or any(address in network for network in _TRANSITION)
            )
        )
    ):
        raise ToolError("TOOL_FORBIDDEN")
    return canonical


async def checked_addresses(
    request: httpx.Request, allowed_addresses: tuple[str, ...]
) -> list[str]:
    """Check every A/AAAA answer, including addresses obtained through CNAMEs."""
    host = request.url.raw_host.decode("ascii")
    port = request.url.port or (443 if request.url.scheme == "https" else 80)
    try:
        ipaddress.ip_address(host)
    except ValueError:
        try:
            async with asyncio.timeout(request.extensions.get("timeout", {}).get("connect")):
                answers = await asyncio.get_running_loop().getaddrinfo(
                    host, port, type=socket.SOCK_STREAM
                )
        except TimeoutError:
            raise httpx.ConnectTimeout("Source DNS timeout") from None
        except OSError:
            raise httpx.ConnectError("Source DNS failed") from None
        addresses = sorted({str(answer[4][0]) for answer in answers})
    else:
        addresses = [host]
    if not addresses:
        raise httpx.ConnectError("Source DNS failed")
    return [permitted_address(address, allowed_addresses) for address in addresses]


def pinned_request(request: httpx.Request, address: str) -> httpx.Request:
    # Numeric connect address; preserve original Host and certificate/SNI hostname.
    return httpx.Request(
        request.method,
        request.url.copy_with(host=address),
        headers=request.headers,
        stream=request.stream,
        extensions={**request.extensions, "sni_hostname": request.url.raw_host.decode("ascii")},
    )


def public_source_url(value: str, *, allow_http: bool = False) -> httpx.URL:
    try:
        parsed = urlsplit(value)
        url = httpx.URL(value)
        port = parsed.port
        if (
            len(value) > 2048
            or len(str(url)) > 2048
            or any(c.isspace() or unicodedata.category(c).startswith("C") for c in value)
            or "\\" in value
            or "@" in parsed.netloc
            or "%" in parsed.netloc
            or not url.host
            or url.scheme not in ({"https", "http"} if allow_http else {"https"})
            or port not in (None, 443 if url.scheme == "https" else 80)
        ):
            raise ToolError("TOOL_FORBIDDEN")
        host = url.host.rstrip(".").lower()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if "." not in host or host.endswith((".local", ".internal", ".localhost")):
                raise ToolError("TOOL_FORBIDDEN") from None
        else:
            permitted_address(host, ())
        return url.copy_with(fragment=None)
    except (ValueError, httpx.InvalidURL):
        raise ToolError("TOOL_FORBIDDEN") from None


@dataclass
class _ConnectionSlot:
    transport: httpx.AsyncHTTPTransport
    origin: tuple[str, bytes, int | None] | None = None


class _OriginStream(httpx.AsyncByteStream):
    def __init__(
        self,
        stream: httpx.AsyncByteStream,
        slot: _ConnectionSlot,
        available: asyncio.Queue[_ConnectionSlot],
    ) -> None:
        self._stream, self._slot, self._available = stream, slot, available
        self._closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in self._stream:
            yield chunk

    async def aclose(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                await self._stream.aclose()
            finally:
                self._available.put_nowait(self._slot)


def _source_pool() -> httpx.AsyncHTTPTransport:
    return httpx.AsyncHTTPTransport(
        trust_env=False,
        verify=True,
        retries=0,
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        http1=True,
        http2=False,
    )


class PublicSourceTransport(httpx.AsyncBaseTransport):
    """Public GET policy without any SearXNG private-address exception."""

    def __init__(self, *, allow_http: bool = False) -> None:
        self._allow_http = allow_http
        self._connections = [_ConnectionSlot(_source_pool()) for _ in range(4)]
        self._available: asyncio.Queue[_ConnectionSlot] = asyncio.Queue(4)
        for slot in self._connections:
            self._available.put_nowait(slot)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if (
            request.method != "GET"
            or public_source_url(str(request.url), allow_http=self._allow_http) != request.url
        ):
            raise ToolError("TOOL_FORBIDDEN")
        checked = await checked_addresses(request, ())
        # All DNS answers have passed the policy. Prefer IPv4 for dual-stack
        # sources so IPv4-only container networks can reach them; retain IPv6-only
        # sources, one pinned connection, and the original Host/TLS SNI binding.
        address = min(checked, key=lambda value: (ipaddress.ip_address(value).version, value))
        origin = (request.url.scheme, request.url.raw_host, request.url.port)
        slot = await self._available.get()
        try:
            # httpcore's pinned origin is an IP. Never reuse TLS from another
            # hostname on that IP: SNI/certificate checks happen at connection time.
            if slot.origin != origin:
                await slot.transport.aclose()
                slot.transport = _source_pool()
                slot.origin = origin
            response = await slot.transport.handle_async_request(pinned_request(request, address))
            if not isinstance(response.stream, httpx.AsyncByteStream):
                raise ToolError("PROVIDER_ERROR")
            response.stream = _OriginStream(response.stream, slot, self._available)
            return response
        except BaseException:
            self._available.put_nowait(slot)
            raise

    async def aclose(self) -> None:
        await asyncio.gather(*(slot.transport.aclose() for slot in self._connections))


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
        checked = await checked_addresses(request, self._allowed_addresses)
        if request.url.scheme != "https" and any(
            ipaddress.ip_address(address).is_global for address in checked
        ):
            raise ToolError("TOOL_FORBIDDEN")
        # No second hostname resolution, redirect or address fallback. Preserve Host
        # and TLS SNI/certificate verification for the configured hostname.
        return await self._transport.handle_async_request(pinned_request(request, checked[0]))

    async def aclose(self) -> None:
        await self._transport.aclose()
