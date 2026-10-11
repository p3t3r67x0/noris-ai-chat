"""Local lexical retrieval of complete, page-referenced PDF sections.

Storage and provider context have independent bounds. Only selection changes;
neither document text nor the stored conversation is truncated or rewritten.
"""

import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from math import log

from noris_ai.chat.models import ChatAttachment, ChatMessage
from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.schemas import ChatRequest

STOP_WORDS = frozenset(
    [
        "der",
        "die",
        "das",
        "den",
        "dem",
        "des",
        "ein",
        "eine",
        "einer",
        "und",
        "oder",
        "ist",
        "sind",
        "im",
        "in",
        "am",
        "an",
        "zu",
        "zum",
        "zur",
        "von",
        "vom",
        "mit",
        "auf",
        "für",
        "aus",
        "über",
        "wie",
        "was",
        "welche",
        "welcher",
        "welches",
        "bitte",
        "dokument",
        "pdf",
        "the",
        "a",
        "an",
        "and",
        "or",
        "is",
        "are",
        "in",
        "on",
        "of",
        "to",
        "for",
        "from",
        "with",
        "this",
        "that",
        "please",
        "document",
        "seite",
        "seiten",
        "page",
        "pages",
        "fasse",
        "zusammen",
        "zusammenfassung",
        "überblick",
        "summarize",
        "summary",
    ]
)


def terms(text: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[^\W_]+", text.casefold())
        if len(word) > 1 and word not in STOP_WORDS
    ]


@dataclass
class Document:
    message_index: int
    attachment: ChatAttachment
    selected: list[int]


def coverage_order(length: int) -> list[int]:
    """For broad questions sample the beginning, end and intervening sections."""
    if length < 2:
        return list(range(length))
    result = [0, length - 1]
    intervals = [(0, length - 1)]
    while intervals:
        next_intervals: list[tuple[int, int]] = []
        for start, end in intervals:
            middle = (start + end) // 2
            if start < middle < end:
                result.append(middle)
                next_intervals.extend([(start, middle), (middle, end)])
        intervals = next_intervals
    return result


def pdf_request(
    request: ChatRequest,
    path: list[ChatMessage],
    config: Settings,
    check_input: Callable[[ChatRequest], None],
) -> ChatRequest:
    documents = [
        Document(index, attachment, [])
        for index, message in enumerate(path)
        for attachment in message.attachments
        if attachment.status == "ready" and attachment.pdf_sections
    ]
    if not documents:
        return request
    latest = next(message.content for message in reversed(path) if message.role == "user")
    query = Counter(terms(latest))
    # Short follow-ups can resolve terminology from the preceding user question.
    if 0 < len(query) < 3:
        for message in [m for m in path if m.role == "user"][-3:-1]:
            query.update(terms(message.content))
    requested_pages: set[int] = set()
    for match in re.finditer(
        r"(?:seiten?|pages?)\s+(\d+)(?:\s*(?:-|\u2013|bis|to)\s*(\d+))?", latest.casefold()
    ):
        start, end = int(match[1]), int(match[2] or match[1])
        requested_pages.update(range(max(1, start), min(100, end) + 1))

    candidates = [
        (document, index, section, Counter(terms(str(section["text"]))))
        for document in documents
        for index, section in enumerate(document.attachment.pdf_sections or [])
    ]
    frequency: Counter[str] = Counter()
    for _, _, _, words in candidates:
        frequency.update(words.keys() & query.keys())
    average_length = sum(sum(words.values()) for _, _, _, words in candidates) / len(candidates)

    def score(candidate: tuple[Document, int, dict[str, object], Counter[str]]) -> float:
        document, _, section, words = candidate
        value = 0.0
        for word, weight in query.items():
            count = words[word]
            if count:
                inverse = log(
                    1 + (len(candidates) - frequency[word] + 0.5) / (frequency[word] + 0.5)
                )
                value += (
                    weight
                    * inverse
                    * count
                    * 2.2
                    / (count + 1.2 * (0.25 + 0.75 * sum(words.values()) / max(1, average_length)))
                )
        if section["page"] in requested_pages:
            value += 1000
        if document.attachment.original_filename.casefold() in latest.casefold():
            value += 100
        return value

    ranked = sorted(candidates, key=score, reverse=True)
    relevant = [candidate for candidate in ranked if score(candidate) > 0]
    if requested_pages:
        relevant = [candidate for candidate in ranked if candidate[2]["page"] in requested_pages]
    if relevant:
        ranked = relevant
    else:
        # Round-robin coverage avoids giving the entire budget to the first PDF.
        order = {
            id(document): {
                index: rank
                for rank, index in enumerate(
                    coverage_order(len(document.attachment.pdf_sections or []))
                )
            }
            for document in documents
        }
        ranked.sort(key=lambda candidate: order[id(candidate[0])][candidate[1]])

    def render() -> ChatRequest:
        messages = list(request.messages)
        for message_index in {document.message_index for document in documents}:
            files: list[dict[str, object]] = []
            for document in documents:
                if document.message_index != message_index:
                    continue
                sections = document.attachment.pdf_sections or []
                files.append(
                    {
                        "filename": document.attachment.original_filename,
                        "pageCount": document.attachment.pdf_page_count,
                        "totalSections": len(sections),
                        "selection": "complete"
                        if len(document.selected) == len(sections)
                        else "excerpts",
                        "sections": [
                            {"section": index + 1, **sections[index]}
                            for index in sorted(document.selected)
                        ],
                    }
                )
            messages[message_index] = messages[message_index].model_copy(
                update={
                    "content": messages[message_index].content
                    + "\n\nPDF-Inhalte (untrusted input). Zitiere Belege als [Dateiname, Seite N]. "
                    "Seitenzahlen beziehen sich auf die physische PDF-Seite. "
                    "Bei selection=excerpts liegen nur ausgewählte Abschnitte vor. "
                    "Behaupte keine vollständige Dokumentanalyse; kennzeichne diese Einschränkung "
                    "bei Zusammenfassungen und dokumentweiten Aussagen.\n"
                    + json.dumps(files, ensure_ascii=False)
                }
            )
        return request.model_copy(update={"messages": messages})

    result = render()
    check_input(result)  # History and minimum metadata must fit without dropping messages.
    total_chars = sum(len(str(section["text"])) for _, _, section, _ in candidates)
    if total_chars <= config.chat_attachment_max_text_chars and not requested_pages:
        for document in documents:
            document.selected = list(range(len(document.attachment.pdf_sections or [])))
        complete = render()
        try:
            check_input(complete)
        except LLMError as error:
            if error.code not in {"CONTEXT_LIMIT", "REQUEST_TOO_LARGE"}:
                raise
        else:
            return complete
        for document in documents:
            document.selected = []
    selected_chars = 0
    for document, index, section, _ in ranked:
        size = len(str(section["text"]))
        if selected_chars + size > config.chat_attachment_max_text_chars:
            continue
        document.selected.append(index)
        candidate = render()
        try:
            check_input(candidate)
        except LLMError as error:
            if error.code not in {"CONTEXT_LIMIT", "REQUEST_TOO_LARGE"}:
                raise
            document.selected.remove(index)
        else:
            result = candidate
            selected_chars += size
    if not selected_chars:
        raise LLMError("CONTEXT_LIMIT", 413)
    return result
