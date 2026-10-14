"""Bounded SearXNG transport, prepared for P1b but never enabled by importing it."""

import asyncio
import ipaddress
import json
import unicodedata
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Literal, Self
from urllib.parse import parse_qsl, urlencode, urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from noris_ai.tools.errors import ToolError
from noris_ai.tools.providers.network import EndpointTransport, permitted_address
from noris_ai.tools.registry import canonical_payload, unique_keys
from noris_ai.tools.schemas import (
    SEARCH_INPUT_BYTES,
    SEARCH_OUTPUT_BYTES,
    SearchInput,
    SearchResult,
    SearchSource,
    search_source_id,
)

FailureReason = Literal[
    "forbidden",
    "rate_limit",
    "server_error",
    "http_error",
    "redirect",
    "connection_error",
    "timeout",
    "invalid_response",
    "response_too_large",
]


class SearXNGError(ToolError):
    """Safe runtime code plus a fixed diagnostic reason, never an upstream message."""

    def __init__(self, reason: FailureReason, *, status_code: int | None = None) -> None:
        super().__init__(
            "TOOL_TIMEOUT"
            if reason == "timeout"
            else "PROVIDER_RATE_LIMIT"
            if reason == "rate_limit"
            else "PROVIDER_ERROR"
        )
        self.reason = reason
        self.status_code = status_code


class SearXNGSettings(BaseSettings):
    """Operator-only configuration. No implicit endpoint, dotenv file or browser fields."""

    model_config = SettingsConfigDict(
        env_prefix="NORIS_SEARXNG_",
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )
    base_url: str = Field(min_length=1, max_length=2048)
    allowed_hosts: tuple[str, ...] = Field(min_length=1, max_length=16)
    allowed_addresses: tuple[str, ...] = Field(default=(), max_length=16)
    config_version: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.:-]+$")
    connect_timeout_seconds: float = Field(default=3, gt=0, le=15, allow_inf_nan=False)
    read_timeout_seconds: float = Field(default=10, gt=0, le=15, allow_inf_nan=False)
    total_timeout_seconds: float = Field(default=15, gt=0, le=15, allow_inf_nan=False)
    max_response_bytes: int = Field(default=1_048_576, ge=1024, le=2_097_152)
    max_results: int = Field(default=8, ge=1, le=8)

    @classmethod
    def from_environment(cls) -> Self:
        return cls.model_validate({})

    @model_validator(mode="after")
    def valid_configuration(self) -> Self:
        try:
            parsed = urlsplit(self.base_url)
            url = httpx.URL(self.base_url)
            port = parsed.port
        except (ValueError, httpx.InvalidURL):
            raise ValueError("Invalid configured SearXNG endpoint") from None
        if (
            url.scheme not in {"http", "https"}
            or not url.host
            or url.host not in self.allowed_hosts
            or "@" in parsed.netloc
            or "?" in self.base_url
            or "#" in self.base_url
            or port == 0
            or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in self.base_url)
            or "\\" in self.base_url
            or "%" in parsed.netloc
        ):
            raise ValueError("SearXNG requires an explicit allowlisted HTTP(S) endpoint")
        if (
            max(self.connect_timeout_seconds, self.read_timeout_seconds)
            > self.total_timeout_seconds
        ):
            raise ValueError("Connection and idle timeouts must fit within the total deadline")
        for address in self.allowed_addresses:
            try:
                if permitted_address(address, self.allowed_addresses) != address:
                    raise ValueError("Noncanonical address")
            except (ValueError, ToolError):
                raise ValueError("Invalid configured SearXNG address") from None
        return self


class _Response(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    results: list[object] = Field(max_length=1000)
    unresponsive_engines: list[object] = Field(default_factory=list[object], max_length=100)


class _Entry(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    title: str
    url: str
    content: str = ""
    publishedDate: object = None


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _plain_text(value: str) -> str:
    parser = _Text()
    parser.feed(value)
    parser.close()
    # These are still untrusted source strings, to be escaped by any future renderer.
    text = " ".join(parser.parts)
    return " ".join(
        "".join(" " if unicodedata.category(c).startswith("C") else c for c in text).split()
    )


def _source_url(value: str) -> HttpUrl | None:
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value) or "\\" in value:
        return None
    try:
        if "@" in urlsplit(value).netloc:
            return None
        url = HttpUrl(value)
        host = (url.host or "").strip("[]").rstrip(".").lower()
        if url.port not in {80, 443} or not host:
            return None
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host or host.endswith((".local", ".internal", ".localhost")):
                return None
        else:
            try:
                permitted_address(str(address), ())
            except ToolError:
                return None
        query = urlencode(
            [
                (key, val)
                for key, val in parse_qsl(url.query or "", keep_blank_values=True)
                if not key.lower().startswith("utm_")
                and key.lower() not in {"fbclid", "gclid", "dclid", "msclkid"}
            ]
        )
        normalized = HttpUrl(
            str(url).split("?", 1)[0].split("#", 1)[0] + ("?" + query if query else "")
        )
        return normalized if len(str(normalized)) <= 2048 else None
    except (ValueError, ValidationError):
        return None


def _published_at(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        date = datetime.fromisoformat(value)
        return date.astimezone(UTC) if date.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def _reject_constant(value: str) -> object:
    raise ValueError("Invalid JSON constant")


def _normalize(payload: bytes, search: SearchInput, config_version: str) -> SearchResult:
    try:
        response = _Response.model_validate(
            json.loads(
                payload.decode("utf-8"),
                object_pairs_hook=unique_keys,
                parse_constant=_reject_constant,
            )
        )
    except (ValueError, RecursionError):
        raise SearXNGError("invalid_response") from None
    if response.unresponsive_engines and not response.results:
        # A reported engine failure without any result is not a genuine zero-hit search.
        raise SearXNGError("server_error")
    sources: list[SearchSource] = []
    seen: set[str] = set()
    warnings: set[str] = set()
    if response.unresponsive_engines:
        warnings.add("SEARCH_ENGINE_FAILURES")
    for row in response.results:
        try:
            entry = _Entry.model_validate(row)
        except ValidationError:
            warnings.add("SEARCH_RESULTS_FILTERED")
            continue
        url = _source_url(entry.url)
        title, snippet = _plain_text(entry.title), _plain_text(entry.content)
        if url is None or not title:
            warnings.add("SEARCH_RESULTS_FILTERED")
            continue
        if str(url) in seen:
            continue
        seen.add(str(url))
        if len(title) > 500 or len(snippet) > 4096:
            warnings.add("SEARCH_TEXT_TRUNCATED")
        published_at = _published_at(entry.publishedDate)
        if entry.publishedDate is not None and published_at is None:
            warnings.add("SEARCH_PUBLICATION_DATE_INVALID")
        sources.append(
            SearchSource(
                source_id=search_source_id(config_version, str(url)),
                title=title[:500],
                url=url,
                snippet=snippet[:4096],
                published_at=published_at,
            )
        )
        if len(sources) == search.limit:
            break
    result = SearchResult(
        sources=sources,
        warnings=sorted(warnings),
        provider="searxng",
        config_version=config_version,
        fetched_at=datetime.now(UTC),
        partial=bool(warnings & {"SEARCH_ENGINE_FAILURES", "SEARCH_RESULTS_FILTERED"}),
    )
    # Character ceilings alone do not guarantee the registry's UTF-8/JSON byte ceiling.
    while len(canonical_payload(result)) > SEARCH_OUTPUT_BYTES:
        index = max(range(len(sources)), key=lambda i: len(sources[i].snippet))
        source = sources[index]
        sources[index] = source.model_copy(
            update={"snippet": source.snippet[: len(source.snippet) // 2]}
        )
        warnings.add("SEARCH_TEXT_TRUNCATED")
        result = result.model_copy(update={"sources": sources, "warnings": sorted(warnings)})
    return SearchResult.model_validate_json(canonical_payload(result))


class SearXNGProvider:
    """Owns bounded HTTP I/O; ToolRuntime owns admission, commit and cancellation."""

    def __init__(
        self,
        settings: SearXNGSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = SearXNGSettings.model_validate(settings.model_dump())
        settings = self._settings
        self._endpoint = settings.base_url.rstrip("/") + "/search"
        self._client = httpx.AsyncClient(
            transport=transport
            if transport is not None
            else EndpointTransport(self._endpoint, settings.allowed_addresses),
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(
                settings.read_timeout_seconds,
                connect=settings.connect_timeout_seconds,
                pool=settings.connect_timeout_seconds,
            ),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
            headers={"Accept": "application/json", "Accept-Encoding": "identity"},
        )
        self._slots = asyncio.Semaphore(4)
        self._closed = False

    @property
    def config_version(self) -> str:
        return self._settings.config_version

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        self._closed = True
        await self._client.aclose()

    async def search(self, search: SearchInput) -> SearchResult:
        if self._closed:
            raise ToolError("TOOL_UNAVAILABLE")
        try:
            search = SearchInput.model_validate(search.model_dump())
        except ValidationError:
            raise ToolError("TOOL_INPUT_INVALID") from None
        if len(canonical_payload(search)) > SEARCH_INPUT_BYTES or any(
            part.startswith(("!", ":", "?")) or (part.startswith("<") and part[1:].isdigit())
            for part in search.query.split()
        ):
            # SearXNG recognizes operators at whitespace-delimited token boundaries.
            raise ToolError("TOOL_INPUT_INVALID")
        search = search.model_copy(update={"limit": min(search.limit, self._settings.max_results)})
        data = {
            "q": search.query.strip(),
            "format": "json",
            "language": search.language,
            "categories": "general",
            "pageno": "1",
            "safesearch": "1",
        }
        if search.time_range is not None:
            data["time_range"] = search.time_range
        try:
            # Admission must be acquired before the HTTP context opens its stream.
            async with asyncio.timeout(self._settings.total_timeout_seconds), self._slots:  # noqa: SIM117
                async with self._client.stream("POST", self._endpoint, data=data) as response:
                    status = response.status_code
                    if status == 403:
                        raise SearXNGError("forbidden", status_code=status)
                    if status == 429:
                        raise SearXNGError("rate_limit", status_code=status)
                    if status >= 500:
                        raise SearXNGError("server_error", status_code=status)
                    if 300 <= status < 400:
                        raise SearXNGError("redirect", status_code=status)
                    if status != 200:
                        raise SearXNGError("http_error", status_code=status)
                    if (
                        response.headers.get("content-type", "").split(";", 1)[0].strip()
                        != "application/json"
                        or response.headers.get("content-encoding", "identity") != "identity"
                    ):
                        raise SearXNGError("invalid_response")
                    body = bytearray()
                    async for chunk in response.aiter_raw(chunk_size=8192):
                        if len(body) + len(chunk) > self._settings.max_response_bytes:
                            raise SearXNGError("response_too_large")
                        body.extend(chunk)
                    return _normalize(bytes(body), search, self._settings.config_version)
        except (TimeoutError, httpx.TimeoutException):
            raise SearXNGError("timeout") from None
        except httpx.RequestError:
            raise SearXNGError("connection_error") from None
