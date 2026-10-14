"""Deterministic, cooperative extraction without a DOM, scripts or external services."""

import asyncio
import re
import unicodedata
from html.parser import HTMLParser
from time import monotonic

from noris_ai.tools.cancellation import GenerationToolContext
from noris_ai.tools.errors import ToolError

_DROP = frozenset(
    {
        "head",
        "script",
        "style",
        "noscript",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "template",
        "iframe",
        "object",
        "embed",
        "svg",
        "canvas",
        "button",
        "select",
        "textarea",
    }
)
_VOID = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
_BLOCK = frozenset(
    {
        "p",
        "div",
        "section",
        "article",
        "main",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "ul",
        "ol",
        "blockquote",
        "pre",
        "tr",
        "table",
        "br",
        "hr",
    }
)
_NOISE = re.compile(
    r"(?:^|[\s_-])(?:ads?|advert\w*|tracking|cookie|navigation|sidebar)(?:$|[\s_-])", re.IGNORECASE
)


class ArticleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool, bool]] = []
        self.parts: list[str] = []
        self.primary: list[str] = []
        self.nodes = 0
        self.excluded_text = False

    def _tick(self) -> None:
        self.nodes += 1
        if self.nodes > 50_000:
            raise ToolError("TOOL_OUTPUT_INVALID")

    def _append(self, text: str) -> None:
        if self.stack and self.stack[-1][1]:
            self.excluded_text |= bool(text.strip())
            return
        self.parts.append(text)
        if self.stack and self.stack[-1][2]:
            self.primary.append(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tick()
        if len(self.stack) >= 128 or len(attrs) > 128:
            raise ToolError("TOOL_OUTPUT_INVALID")
        attributes = dict(attrs)
        style = re.sub(r"\s+", "", attributes.get("style") or "").lower()
        hidden = (
            tag in _DROP
            or "hidden" in attributes
            or (attributes.get("aria-hidden") or "").lower() == "true"
            or "display:none" in style
            or "visibility:hidden" in style
            or bool(
                _NOISE.search((attributes.get("class") or "") + " " + (attributes.get("id") or ""))
            )
        )
        suppressed = hidden or bool(self.stack and self.stack[-1][1])
        primary = tag in {"main", "article"} or bool(self.stack and self.stack[-1][2])
        if tag not in _VOID:
            self.stack.append((tag, suppressed, primary))
        if tag in _BLOCK and not suppressed:
            self._append("\n\n")
        elif tag in {"td", "th"} and not suppressed:
            self._append(" ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        self._tick()
        if tag in _BLOCK:
            self._append("\n\n")
        # Bound malformed nesting. Unmatched closing tags never unsuppress content.
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data: str) -> None:
        self._tick()
        self._append(data)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    value = "".join(
        c
        if c == "\n"
        else " "
        if c.isspace()
        else ""
        if unicodedata.category(c).startswith("C")
        else c
        for c in value
    )
    lines = [" ".join(line.split()) for line in value.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


async def extract_text(body: bytes, mime: str, charset: str, context: GenerationToolContext) -> str:
    context.check()
    if body.startswith(
        (b"%PDF-", b"PK\x03\x04", b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF", b"OggS", b"ID3")
    ):
        raise ToolError("TOOL_OUTPUT_INVALID")
    try:
        decoded = body.decode(charset, errors="strict")
    except (UnicodeError, LookupError):
        raise ToolError("TOOL_OUTPUT_INVALID") from None
    decoded = decoded.removeprefix("\ufeff")
    start = monotonic()
    if mime == "text/html":
        parser = ArticleText()
        for offset in range(0, len(decoded), 4096):
            context.check()
            if monotonic() - start > 2:
                raise ToolError("TOOL_TIMEOUT")
            parser.feed(decoded[offset : offset + 4096])
            await asyncio.sleep(0)
        parser.close()
        text = normalize_text(
            "".join(parser.primary if any(p.strip() for p in parser.primary) else parser.parts)
        )
        if not text and parser.excluded_text:
            raise ToolError("TOOL_OUTPUT_INVALID")
    else:
        text = normalize_text(decoded)
    context.check()
    if monotonic() - start > 2:
        raise ToolError("TOOL_TIMEOUT")
    return text
