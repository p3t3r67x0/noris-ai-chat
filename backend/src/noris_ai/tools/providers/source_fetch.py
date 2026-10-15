"""Bounded public source HTTP; no tool persistence, credentials or follow-up actions."""

import asyncio
import hashlib
import logging
import re
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from threading import Lock
from typing import Literal, Self
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

from noris_ai.chat.repository import utc_now
from noris_ai.tools.cancellation import GenerationToolContext
from noris_ai.tools.errors import ToolError
from noris_ai.tools.extraction import extract_text
from noris_ai.tools.providers.network import PublicSourceTransport, public_source_url
from noris_ai.tools.registry import canonical_payload
from noris_ai.tools.schemas import SourceDocument

_CONTENT_TYPE = re.compile(
    r'(text/html|text/plain)(?:\s*;\s*charset\s*=\s*(?:"([a-z0-9_-]+)"|([a-z0-9_-]+)))?\s*',
    re.IGNORECASE,
)
_CHARSETS = {
    "utf-8": "utf-8",
    "utf8": "utf-8",
    "us-ascii": "ascii",
    "ascii": "ascii",
    "iso-8859-1": "latin-1",
    "windows-1252": "cp1252",
}
MAX_DOWNLOAD_BYTES = 1_048_576
MAX_DECOMPRESSED_BYTES = 2_097_152
MAX_HEADER_BYTES = 16_384
MAX_REDIRECTS = 3
_FETCH_HEADERS = {
    "Accept": "text/html, text/plain",
    "Accept-Encoding": "gzip, identity",
    "User-Agent": "noris-ai-source-fetch/1",
}
_BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, identity",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="99", "Google Chrome";v="140"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
}
_FETCH_LOG_SCOPE: ContextVar[bool] = ContextVar("source_fetch_log_scope", default=False)


class _FetchLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # HTTPX logs complete URLs; httpcore DEBUG includes response headers.
        # Suppress only this task's fetch traffic, leaving unrelated clients intact.
        return not _FETCH_LOG_SCOPE.get()


_FETCH_LOG_FILTER = _FetchLogFilter()
_FETCH_LOG_LOCK = Lock()
_fetch_log_users = 0
_FETCH_LOGGERS = tuple(
    logging.getLogger(name)
    for name in (
        "httpx",
        "httpcore.connection",
        "httpcore.http11",
        "httpcore.http2",
        "hpack.hpack",
        "hpack.table",
    )
)


@contextmanager
def _fetch_logging() -> Iterator[None]:
    global _fetch_log_users
    with _FETCH_LOG_LOCK:
        if _fetch_log_users == 0:
            for logger in _FETCH_LOGGERS:
                logger.addFilter(_FETCH_LOG_FILTER)
        _fetch_log_users += 1
    token = _FETCH_LOG_SCOPE.set(True)
    try:
        yield
    finally:
        _FETCH_LOG_SCOPE.reset(token)
        with _FETCH_LOG_LOCK:
            _fetch_log_users -= 1
            if _fetch_log_users == 0:
                for logger in _FETCH_LOGGERS:
                    logger.removeFilter(_FETCH_LOG_FILTER)


def redirect_target(response: httpx.Response, *, allow_http: bool) -> httpx.URL:
    locations = response.headers.get_list("location")
    if (
        len(locations) != 1
        or len(locations[0]) > 2048
        or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in locations[0])
        or "\\" in locations[0]
    ):
        raise ToolError("TOOL_FORBIDDEN")
    try:
        if urlsplit(locations[0]).scheme not in {"", "https", "http"}:
            raise ToolError("TOOL_FORBIDDEN")
        target = public_source_url(
            str(response.request.url.join(locations[0])), allow_http=allow_http
        )
    except (ValueError, httpx.InvalidURL):
        raise ToolError("TOOL_FORBIDDEN") from None
    if response.request.url.scheme == "https" and target.scheme != "https":
        raise ToolError("TOOL_FORBIDDEN")
    return target


class SourceFetchSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NORIS_SOURCE_FETCH_",
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )
    # Version describes this deterministic policy/extractor, independent of SearXNG config.
    config_version: Literal["p7a-v1"] = "p7a-v1"
    allow_http: bool = False


def response_metadata(
    response: httpx.Response,
) -> tuple[Literal["text/html", "text/plain"], str, str]:
    headers = response.headers
    if sum(len(k) + len(v) for k, v in headers.raw) > MAX_HEADER_BYTES or len(headers.raw) > 100:
        raise ToolError("TOOL_OUTPUT_INVALID")
    for name in ("content-type", "content-encoding", "content-length", "transfer-encoding"):
        if len(headers.get_list(name)) > 1:
            raise ToolError("TOOL_OUTPUT_INVALID")
    match = _CONTENT_TYPE.fullmatch(headers.get("content-type", ""))
    if match is None:
        raise ToolError("TOOL_OUTPUT_INVALID")
    mime: Literal["text/html", "text/plain"] = (
        "text/html" if match[1].lower() == "text/html" else "text/plain"
    )
    charset = _CHARSETS.get((match[2] or match[3] or "utf-8").lower())
    encoding = headers.get("content-encoding", "identity").strip().lower()
    transfer = headers.get("transfer-encoding", "").strip().lower()
    length = headers.get("content-length")
    if (
        charset is None
        or encoding not in {"identity", "gzip"}
        or transfer not in {"", "chunked"}
        or (transfer and length is not None)
        or (
            length is not None
            and (
                not length.isascii()
                or not length.isdigit()
                or len(length) > 10
                or int(length) > MAX_DOWNLOAD_BYTES
            )
        )
    ):
        raise ToolError("TOOL_OUTPUT_INVALID")
    return mime, charset, encoding


def bounded_document(
    source_id: UUID,
    fetched_at: datetime,
    text: str,
    mime: Literal["text/html", "text/plain"],
    url: httpx.URL,
    *,
    max_output_bytes: int,
) -> SourceDocument:
    # Fit the actual canonical JSON, including escaped newlines and all metadata.
    # PostgreSQL jsonb::text includes spaces between fields. Keep that constraint
    # below the same ceiling without changing the registry contract.
    max_output_bytes -= 64

    def document(size: int) -> SourceDocument:
        final = text[:size]
        return SourceDocument(
            source_id=source_id,
            text=final,
            digest=hashlib.sha256(final.encode("utf-8")).hexdigest(),
            mime=mime,
            final_url=HttpUrl(str(url)),
            fetched_at=fetched_at,
        )

    low, high = 0, min(len(text), 65_536)
    while low < high:
        mid = (low + high + 1) // 2
        if len(canonical_payload(document(mid))) <= max_output_bytes:
            low = mid
        else:
            high = mid - 1
    result = document(low)
    if len(canonical_payload(result)) > max_output_bytes:
        raise ToolError("TOOL_OUTPUT_INVALID")
    return result


class SourceFetchProvider:
    def __init__(
        self, settings: SourceFetchSettings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._settings = SourceFetchSettings.model_validate(settings.model_dump())

        async def check_redirect(response: httpx.Response) -> None:
            # HTTPX constructs next_request even with follow_redirects=False.
            # Check the raw Location before its automatic redirect parser runs.
            if response.status_code in {301, 302, 303, 307, 308}:
                redirect_target(response, allow_http=self._settings.allow_http)

        self._client = httpx.AsyncClient(
            transport=transport
            if transport is not None
            else PublicSourceTransport(allow_http=settings.allow_http),
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(3, connect=2, pool=2),
            event_hooks={"response": [check_redirect]},
        )
        self._slots = asyncio.Semaphore(4)
        self._closed = False

    @property
    def config_version(self) -> str:
        return self._settings.config_version + ("-http" if self._settings.allow_http else "")

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        self._closed = True
        await self._client.aclose()

    async def fetch(
        self,
        context: GenerationToolContext,
        source_id: UUID,
        source_url: str,
        *,
        max_output_bytes: int,
    ) -> SourceDocument:
        context.check()
        if self._closed:
            raise ToolError("TOOL_UNAVAILABLE")
        url = public_source_url(source_url, allow_http=self._settings.allow_http)
        visited: set[str] = set()
        browser_headers = False
        browser_retry = False
        downloaded = 0
        with _fetch_logging():
            try:
                async with (
                    asyncio.timeout(
                        min(10, max(0, (context.deadline_at - utc_now()).total_seconds()))
                    ),
                    self._slots,
                ):
                    for hop in range(MAX_REDIRECTS + 1):
                        context.check()
                        if self._closed:
                            raise ToolError("TOOL_UNAVAILABLE")
                        if str(url) in visited and not browser_retry:
                            raise ToolError("TOOL_FORBIDDEN")
                        browser_retry = False
                        visited.add(str(url))
                        # Build every request from scratch: no cookie jar, auth, referrer
                        # or headers carried over from responses or redirect destinations.
                        request = httpx.Request(
                            "GET",
                            url,
                            headers=_BROWSER_HEADERS if browser_headers else _FETCH_HEADERS,
                        )
                        response = await self._client.send(request, stream=True)
                        self._client.cookies.clear()
                        try:
                            context.check()
                            if (
                                sum(len(k) + len(v) for k, v in response.headers.raw)
                                > MAX_HEADER_BYTES
                                or len(response.headers.raw) > 100
                            ):
                                raise ToolError("TOOL_OUTPUT_INVALID")
                            if response.status_code in {301, 302, 303, 307, 308}:
                                if hop == MAX_REDIRECTS:
                                    raise ToolError("TOOL_FORBIDDEN")
                                url = redirect_target(
                                    response, allow_http=self._settings.allow_http
                                )
                                continue
                            if response.status_code == 429:
                                raise ToolError("PROVIDER_RATE_LIMIT")
                            if (
                                response.status_code == 403
                                and not browser_headers
                                and hop < MAX_REDIRECTS
                            ):
                                # One compatibility attempt at the same validated URL;
                                # it consumes an existing hop and keeps the same byte,
                                # cancellation, deadline, DNS and TLS limits. Response
                                # cookies/headers and browser credentials stay excluded.
                                browser_headers = browser_retry = True
                                continue
                            if response.status_code != 200:
                                raise ToolError("PROVIDER_ERROR")
                            mime, charset, encoding = response_metadata(response)
                            inflater = zlib.decompressobj(31) if encoding == "gzip" else None
                            body = bytearray()
                            async for raw in response.aiter_raw(chunk_size=16_384):
                                context.check()
                                downloaded += len(raw)
                                if downloaded > MAX_DOWNLOAD_BYTES:
                                    raise ToolError("TOOL_OUTPUT_INVALID")
                                decoded = (
                                    inflater.decompress(raw, MAX_DECOMPRESSED_BYTES - len(body) + 1)
                                    if inflater is not None
                                    else raw
                                )
                                if len(body) + len(decoded) > MAX_DECOMPRESSED_BYTES or (
                                    inflater is not None
                                    and (inflater.unconsumed_tail or inflater.unused_data)
                                ):
                                    raise ToolError("TOOL_OUTPUT_INVALID")
                                body.extend(decoded)
                                await asyncio.sleep(0)
                            if inflater is not None and not inflater.eof:
                                raise ToolError("TOOL_OUTPUT_INVALID")
                            fetched_at = utc_now()
                            text = await extract_text(bytes(body), mime, charset, context)
                            result = bounded_document(
                                source_id,
                                fetched_at,
                                text,
                                mime,
                                url,
                                max_output_bytes=max_output_bytes,
                            )
                            context.check()
                            return result
                        finally:
                            await response.aclose()
            except (TimeoutError, httpx.TimeoutException):
                raise ToolError("TOOL_TIMEOUT") from None
            except (httpx.RequestError, httpx.InvalidURL):
                raise ToolError("PROVIDER_ERROR") from None
            except zlib.error:
                raise ToolError("TOOL_OUTPUT_INVALID") from None
            finally:
                self._client.cookies.clear()
            raise ToolError("TOOL_FORBIDDEN")
