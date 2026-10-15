"""Real-browser retrieval regressions with controlled HTTP/HTML, no external traffic."""

import logging
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import hpack
import httpx
import pytest

from noris_ai.tools.errors import ToolError
from noris_ai.tools.extraction import extract_text
from noris_ai.tools.providers.source_fetch import (
    SourceFetchProvider,
    SourceFetchSettings,
)
from tests.unit.test_source_fetch import fetch_context, response


async def test_browser_compatibility_is_one_same_url_attempt_without_response_credentials():
    requests: list[httpx.Request] = []

    def network(request: httpx.Request):
        requests.append(request)
        assert "cookie" not in request.headers
        assert "authorization" not in request.headers and "referer" not in request.headers
        if len(requests) == 1:
            assert request.headers["user-agent"] == "noris-ai-source-fetch/1"
            return response(status=403, headers={"Set-Cookie": "private=secret"})
        assert "Mozilla/5.0" in request.headers["user-agent"]
        assert request.headers["accept-language"].startswith("de-DE")
        assert request.headers["sec-fetch-mode"] == "navigate"
        return response(b"<article>Public profile</article>")

    async with SourceFetchProvider(
        SourceFetchSettings(), transport=httpx.MockTransport(network)
    ) as provider:
        document = await provider.fetch(
            fetch_context(), uuid4(), "https://source.example.org/profile", max_output_bytes=262144
        )
    assert document.text == "Public profile"
    assert len(requests) == 2 and requests[0].url == requests[1].url
    assert str(requests[1].url) == str(document.final_url)


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
async def test_protection_and_provider_errors_do_not_trigger_unbounded_retries(status: int):
    requests: list[httpx.Request] = []

    def network(request: httpx.Request):
        requests.append(request)
        return response(status=status)

    async with SourceFetchProvider(
        SourceFetchSettings(), transport=httpx.MockTransport(network)
    ) as provider:
        with pytest.raises(ToolError, match=r"PROVIDER_RATE_LIMIT|PROVIDER_ERROR"):
            await provider.fetch(
                fetch_context(), uuid4(), "https://source.example.org/", max_output_bytes=262144
            )
    assert len(requests) == (2 if status == 403 else 1)


async def test_compatibility_attempt_consumes_existing_redirect_limit():
    requests: list[httpx.Request] = []

    def network(request: httpx.Request):
        requests.append(request)
        if len(requests) == 2:
            return response(status=403)
        return response(status=302, headers={"Location": f"/page-{len(requests)}"})

    async with SourceFetchProvider(
        SourceFetchSettings(), transport=httpx.MockTransport(network)
    ) as provider:
        with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
            await provider.fetch(
                fetch_context(), uuid4(), "https://source.example.org/", max_output_bytes=262144
            )
    assert len(requests) == 4
    assert requests[1].url == requests[2].url


async def test_cancel_fence_blocks_browser_attempt():
    context = fetch_context()
    requests: list[httpx.Request] = []

    def network(request: httpx.Request):
        requests.append(request)
        context.cancellation.event.set()
        return response(status=403)

    async with SourceFetchProvider(
        SourceFetchSettings(), transport=httpx.MockTransport(network)
    ) as provider:
        with pytest.raises(ToolError, match="TOOL_CANCELLED"):
            await provider.fetch(
                context, uuid4(), "https://source.example.org/", max_output_bytes=262144
            )
    assert len(requests) == 1


async def test_http2_hpack_logs_hide_headers_and_query_only_inside_fetch(
    caplog: pytest.LogCaptureFixture,
):
    caplog.set_level(logging.DEBUG)
    headers = [
        (b":path", b"/public?private-fetch-query"),
        (b"cookie", b"private-fetch-cookie"),
    ]

    def network(request: httpx.Request):
        logging.getLogger("httpcore.http2").debug("response private-fetch-cookie")
        encoder, decoder = hpack.Encoder(), hpack.Decoder()
        decoder.decode(encoder.encode(headers))
        encoder.header_table_size = 0  # Exercise hpack.table's eviction logging too.
        encoder.encode([(b":path", b"/private-fetch-query")])
        return response()

    async with SourceFetchProvider(
        SourceFetchSettings(), transport=httpx.MockTransport(network)
    ) as provider:
        await provider.fetch(
            fetch_context(), uuid4(), "https://source.example.org/", max_output_bytes=262144
        )
    assert "private-fetch" not in caplog.text
    hpack.Decoder().decode(hpack.Encoder().encode([(b":path", b"/unrelated-visible")]))
    assert "unrelated-visible" in caplog.text


def react_helper() -> str:
    helper = (Path(__file__).parents[1] / "fixtures/react-fizz-reveal.js").read_text()
    return helper.split("// fixture:payload\n", 1)[1].removesuffix("\n")


def streamed_html(segment: str = '<div hidden id="S:0"><main>Profile biography</main></div>'):
    return (
        '<!--$?--><template id="B:0"></template><!--/$-->'
        + segment
        + "<script>"
        + react_helper()
        + '$RC("B:0","S:0")</script>'
    ).encode()


HIDDEN_CHANGES: list[Callable[[bytes], bytes]] = [
    lambda body: body.replace(b'<template id="B:0"></template>', b""),
    lambda body: body.replace(b'$RC("B:0","S:0")', b'$RX("B:0","S:0")'),
    lambda body: body.replace(b'$RC("B:0","S:0")', b'$RC("B:9","S:0")'),
    lambda body: body.replace(b"<script>", b'<script type="text/plain">'),
    lambda body: body.replace(b'$RC("B:0","S:0")', b'/*$RC("B:0","S:0")*/'),
    lambda body: body.replace(b'$RC("B:0","S:0")', b'const x=\'$RC("B:0","S:0")\''),
    lambda body: body.replace(
        b'<template id="B:0"></template>',
        b'<section hidden><template id="B:0"></template></section>',
    ),
    lambda body: body.replace(
        b'<template id="B:0"></template>',
        b'<section style="display:none"><template id="B:0"></template></section>',
    ),
    lambda body: body.replace(b"<script>", b"<p>").replace(b"</script>", b"</p>"),
    lambda body: body.replace(b"<script>", b'<script type="application/json">').replace(
        b'$RC("B:0","S:0")', b'"$RC(\\"B:0\\",\\"S:0\\")"'
    ),
    lambda body: body.replace(b"hidden id=", b'aria-hidden="true" hidden id='),
    lambda body: body.replace(b"hidden id=", b'hidden="secret" id='),
    lambda body: b"<div hidden>" + body + b"</div>",
]


@pytest.mark.parametrize("change", HIDDEN_CHANGES)
async def test_script_protocol_cannot_reveal_hidden_document_content(
    change: Callable[[bytes], bytes],
):
    # The independent visible paragraph keeps a rejected segment from making the
    # whole document invalid, so this assertion checks exclusion directly.
    body = change(streamed_html()) + b"<p>Visible document</p>"
    text = await extract_text(body, "text/html", "utf-8", fetch_context())
    assert "Profile biography" not in text and "Visible document" in text


async def test_duplicate_streaming_attributes_invalidate_the_document():
    body = streamed_html().replace(b"hidden id=", b"hidden hidden id=")
    with pytest.raises(ToolError, match="TOOL_OUTPUT_INVALID"):
        await extract_text(body, "text/html", "utf-8", fetch_context())


@pytest.mark.parametrize(
    "variant",
    [
        "known-helper",
        "duplicate-id",
        "duplicate-script-type",
        "helper-change",
        "batch-clear",
        "extra-attribute",
        "long-script",
        "external-script",
        "computed-name",
        "before-nodes",
        "bare-callback",
        "nested-chain",
    ],
)
async def test_react_scripts_and_hidden_segments_stay_uninterpreted(variant: str):
    body = streamed_html()
    if variant == "duplicate-id":
        body = b'<div id="S:0" id="other">Other node</div>' + body
    elif variant == "duplicate-script-type":
        body = body.replace(b"<script>", b'<script type="text/plain" type="text/javascript">')
    elif variant == "helper-change":
        body += b"<script>$RC=function(){}</script>"
    elif variant == "batch-clear":
        body += b"<script>$RB.length=0</script>"
    elif variant == "extra-attribute":
        body += b'<script data-extra="1">$RC=function(){}</script>'
    elif variant == "long-script":
        body += b"<script>$RC=function(){};" + b" " * 24000 + b"</script>"
    elif variant == "external-script":
        body += b'<script src="https://source.example.org/script.js"></script>'
    elif variant == "computed-name":
        body += b'<script>window["$"+"RC"]=function(){}</script>'
    elif variant == "before-nodes":
        body = (
            b"<script>" + react_helper().encode() + b'$RC("B:0","S:0")</script>'
            b'<template id="B:0"></template><div hidden id="S:0">Profile biography</div>'
        )
    elif variant == "bare-callback":
        body = body.replace(react_helper().encode(), b"")
    elif variant == "nested-chain":
        body = body.replace(b"Profile biography", b'<div hidden id="S:1">Profile biography</div>')
    body += b"<main>Visible document</main>"
    assert await extract_text(body, "text/html", "utf-8", fetch_context()) == "Visible document"


@pytest.mark.parametrize("kind", ["description", "og:description", "twitter:description"])
async def test_empty_client_rendered_body_uses_only_published_html_description(kind: str):
    body = (
        "<html><head><title>Public profile</title>"
        f'<meta name="{kind}" content="Published biography &amp; photographs">'
        "</head><body><div hidden>Private hidden body</div><script>runBrowser()</script>"
        "</body></html>"
    ).encode()
    assert await extract_text(body, "text/html", "utf-8", fetch_context()) == (
        "Public profile\n\nPublished biography & photographs"
    )


async def test_regular_article_wins_over_html_metadata():
    body = (
        b'<head><meta name="description" content="Different description"></head>'
        b"<main>Actual article</main>"
    )
    assert await extract_text(body, "text/html", "utf-8", fetch_context()) == "Actual article"


@pytest.mark.parametrize(
    "kind", ["body-meta", "template", "script", "duplicate-attributes", "title-only", "unknown-key"]
)
async def test_metadata_fallback_does_not_use_hidden_markup_or_arbitrary_metadata(kind: str):
    meta = '<meta name="description" content="Unusable description">'
    body = {
        "body-meta": "<body>" + meta + "<script>run()</script></body>",
        "template": "<head><template>" + meta + "</template></head>",
        "script": "<head><script>" + meta + "</script></head>",
        "duplicate-attributes": "<head>" + meta.replace("name=", 'name="other" name=') + "</head>",
        "title-only": "<head><title>Title without a document description</title></head>",
        "unknown-key": "<head>" + meta.replace("description", "private-audit") + "</head>",
    }[kind].encode()
    if kind in {"template", "duplicate-attributes", "unknown-key"}:
        # Structurally empty HTML remains compatible with P7a; its existing
        # research-quality gate rejects empty source text for grounding.
        assert await extract_text(body, "text/html", "utf-8", fetch_context()) == ""
    else:
        with pytest.raises(ToolError, match="TOOL_OUTPUT_INVALID"):
            await extract_text(body, "text/html", "utf-8", fetch_context())


async def test_metadata_fallback_limits_title_and_description_and_preserves_unicode():
    body = (
        "<head><title>"
        + "Ä" * 300
        + '</title><meta name="description" content="'
        + "Ü" * 5000
        + '"></head><body><script>run()</script></body>'
    ).encode()
    text = await extract_text(body, "text/html", "utf-8", fetch_context())
    assert text == "Ä" * 256 + "\n\n" + "Ü" * 4096


async def test_metadata_description_priority_is_stable():
    body = (
        b'<head><meta property="og:title" content="Published title">'
        b'<meta property="og:description" content="Preview description">'
        b'<meta name="description" content="Canonical description"></head>'
    )
    assert await extract_text(body, "text/html", "utf-8", fetch_context()) == (
        "Published title\n\nCanonical description"
    )


@pytest.mark.parametrize("region", ["template", "noscript", "body hidden", "div hidden"])
async def test_head_inside_other_regions_is_never_publisher_metadata(region: str):
    closing = region.split()[0]
    body = (
        f'<{region}><head><meta name="description" content="Hidden region description">'
        f"</head></{closing}>"
    ).encode()
    assert await extract_text(body, "text/html", "utf-8", fetch_context()) == ""


@pytest.mark.parametrize(
    "head", ["<head hidden>", '<head aria-hidden="true">', '<head style="display:none">']
)
async def test_explicitly_hidden_head_metadata_is_ignored(head: str):
    body = (head + '<meta name="description" content="Hidden head description"></head>').encode()
    assert await extract_text(body, "text/html", "utf-8", fetch_context()) == ""


async def test_late_head_after_body_is_not_a_metadata_fallback():
    body = b'<body></body><head><meta name="description" content="Late description"></head>'
    assert await extract_text(body, "text/html", "utf-8", fetch_context()) == ""
