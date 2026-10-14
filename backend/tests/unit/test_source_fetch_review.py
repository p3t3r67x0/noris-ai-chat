"""Reproducible findings from the final PR-head security review."""

import asyncio
import logging
import unicodedata
from dataclasses import replace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from pydantic import HttpUrl

from noris_ai.tools.errors import ToolError
from noris_ai.tools.extraction import extract_text, normalize_text
from noris_ai.tools.providers.source_fetch import SourceFetchProvider, SourceFetchSettings
from noris_ai.tools.registry import create_tool_registry
from noris_ai.tools.schemas import FetchInput, SearchSource
from tests.unit.test_source_fetch import fetch_context, response


@pytest.mark.parametrize("control", ["\x00", "\x01", "\u200d", "\u2066"])
def test_final_text_is_nfc_after_removing_controls(control: str) -> None:
    normalized = normalize_text("A" + control + "\u030a")
    assert normalized == "Å"
    assert unicodedata.is_normalized("NFC", normalized)
    assert normalize_text(normalized) == normalized


async def test_unmatched_block_end_tags_do_not_invent_paragraphs() -> None:
    assert (
        await extract_text(b"<main>A</p>B</div>C</main>", "text/html", "utf-8", fetch_context())
        == "ABC"
    )


async def test_logging_filters_have_scoped_lifecycle_and_concurrent_clients(
    caplog: pytest.LogCaptureFixture,
) -> None:
    loggers = [
        logging.getLogger(name) for name in ("httpx", "httpcore.connection", "httpcore.http11")
    ]
    original = [tuple(logger.filters) for logger in loggers]
    entered, release = asyncio.Event(), asyncio.Event()
    caplog.set_level(logging.DEBUG)

    async def network(request: httpx.Request) -> httpx.Response:
        entered.set()
        logging.getLogger("httpcore.http11").debug("fetch header secret-header")
        await release.wait()
        return response()

    first = SourceFetchProvider(
        SourceFetchSettings(), transport=httpx.MockTransport(lambda _: response())
    )
    second = SourceFetchProvider(SourceFetchSettings(), transport=httpx.MockTransport(network))
    try:
        task = asyncio.create_task(
            second.fetch(
                fetch_context(),
                uuid4(),
                "https://source.example.org/?secret-query",
                max_output_bytes=262_144,
            )
        )
        await entered.wait()
        await first.aclose()
        await first.aclose()
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response())) as client:
            await client.get("https://unrelated.example.org/?must-remain-visible")
        release.set()
        await task
        assert "secret-header" not in caplog.text and "secret-query" not in caplog.text
        assert "must-remain-visible" in caplog.text
    finally:
        release.set()
        await first.aclose()
        await second.aclose()
    assert [tuple(logger.filters) for logger in loggers] == original


async def test_http_policy_change_cannot_reuse_https_only_permission() -> None:
    source = SearchSource(
        source_id=uuid4(), title="source", url=HttpUrl("http://source.example.org/"), snippet=""
    )
    resolver = AsyncMock(return_value=source)
    async with SourceFetchProvider(
        SourceFetchSettings(allow_http=True), transport=httpx.MockTransport(lambda _: response())
    ) as p:
        assert p.config_version != "p7a-v1"
        definition = create_tool_registry(source_fetch=p, source_resolver=resolver).get(
            "web.fetch.v1"
        )
        assert definition.handler is not None
        with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
            await definition.handler(fetch_context(), FetchInput(source_id=source.source_id))
        resolver.assert_not_called()
        value = await definition.handler(
            replace(fetch_context(), config_version=p.config_version),
            FetchInput(source_id=source.source_id),
        )
        assert value.final_url.scheme == "http"


async def test_malformed_ancestor_close_cannot_escape_hidden_content() -> None:
    body = b"<main><div hidden>hidden</main>technical secret</div><p>Visible</p></main>"
    assert await extract_text(body, "text/html", "utf-8", fetch_context()) == "Visible"


async def test_incomplete_oversized_markup_does_not_succeed_as_empty() -> None:
    with pytest.raises(ToolError, match="TOOL_OUTPUT_INVALID"):
        await extract_text(b"<a " + b"a= " * 50_000, "text/html", "utf-8", fetch_context())


async def test_attributes_are_bounded_before_parser_allocates_all_nodes() -> None:
    import tracemalloc

    body = b"<a " + b"a=x " * 20_000 + b">text</a>"
    tracemalloc.start()
    try:
        with pytest.raises(ToolError, match="TOOL_OUTPUT_INVALID"):
            await extract_text(body, "text/html", "utf-8", fetch_context())
        _, peak = tracemalloc.get_traced_memory()
        assert peak < 8_388_608
    finally:
        tracemalloc.stop()


async def test_large_visible_text_and_discarded_script_remain_streamable() -> None:
    body = (
        b"<script>" + b"untrusted code;" * 30_000 + b"</script><main>" + b"x" * 100_000 + b"</main>"
    )
    assert await extract_text(body, "text/html", "utf-8", fetch_context()) == "x" * 100_000


async def test_cancel_one_of_two_apps_does_not_remove_other_fetch_log_guard(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("httpcore.http11")
    original = tuple(logger.filters)
    both_entered, release = asyncio.Event(), asyncio.Event()
    entered = 0
    caplog.set_level(logging.DEBUG)

    async def network(request: httpx.Request) -> httpx.Response:
        nonlocal entered
        entered += 1
        if entered == 2:
            both_entered.set()
        logger.debug("private concurrent response header")
        await release.wait()
        logger.debug("private remaining response header")
        return response()

    async with (
        SourceFetchProvider(SourceFetchSettings(), transport=httpx.MockTransport(network)) as first,
        SourceFetchProvider(
            SourceFetchSettings(), transport=httpx.MockTransport(network)
        ) as second,
    ):
        tasks = [
            asyncio.create_task(
                p.fetch(
                    fetch_context(),
                    uuid4(),
                    "https://source.example.org/?private-concurrent-query",
                    max_output_bytes=262_144,
                )
            )
            for p in (first, second)
        ]
        await asyncio.wait_for(both_entered.wait(), 2)
        tasks[0].cancel()
        with pytest.raises(asyncio.CancelledError):
            await tasks[0]
        await first.aclose()
        logger.info("unrelated request remains visible")
        release.set()
        await tasks[1]
    assert "private" not in caplog.text
    assert "unrelated request remains visible" in caplog.text
    assert tuple(logger.filters) == original
