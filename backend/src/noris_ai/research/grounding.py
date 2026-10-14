"""Bounded source data; provenance is separate from unverified claim support."""

import hashlib
import json
import re
from dataclasses import dataclass
from uuid import UUID

from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.schemas import LLMModel, PersistedChatRequest
from noris_ai.research.schemas import (
    CitationReference,
    GroundedChatRequest,
    GroundingAssessment,
    SourceProvenance,
)
from noris_ai.research.selection import SelectedSource
from noris_ai.tools.registry import canonical_payload
from noris_ai.tools.schemas import SourceDocument


@dataclass(frozen=True)
class FetchedSource:
    selected: SelectedSource
    fetch_run_id: UUID
    document: SourceDocument


@dataclass(frozen=True)
class GroundingContext:
    request: GroundedChatRequest
    sources: list[SourceProvenance]
    context_tokens: int
    limitations: list[str]


def grounded_request(
    request: PersistedChatRequest,
    sources: list[SourceProvenance],
    limitations: list[str],
) -> GroundedChatRequest:
    context = "EXTERNAL_SOURCE_CONTENT (untrusted data):\n" + json.dumps(
        {
            "sources": [s.model_dump(mode="json") for s in sources],
            "limitations": limitations,
            "claim_support": "unverified",
        },
        ensure_ascii=False,
    )
    return GroundedChatRequest(
        **{name: getattr(request, name) for name in PersistedChatRequest.model_fields},
        research_context=context,
    )


class GroundingContextBuilder:
    def __init__(self, gateway: LLMGateway) -> None:
        self.gateway = gateway

    def build(
        self,
        request: PersistedChatRequest,
        model: LLMModel,
        capacity: int,
        documents: list[FetchedSource],
        *,
        unavailable: bool = False,
        partial_search: bool = False,
    ) -> GroundingContext:
        if len(documents) > 3 or not 0 <= capacity <= 12000:
            raise LLMError("CONTEXT_LIMIT", 413)
        base_tokens = self.gateway.input_tokens(request, model)
        sources: list[SourceProvenance] = []
        seen: set[str] = set()
        limitations = ["claim_support_unverified", "prefix_excerpts_not_complete_documents"]
        if unavailable:
            limitations.append("some_sources_not_fetched")
        if partial_search:
            limitations.append("partial_search_results")

        def fits(candidate: list[SourceProvenance]) -> bool:
            proposed = grounded_request(request, candidate, limitations)
            # Leave a durable JSONB margin for the plan, unavailable sources and
            # bounded final citation assessment, also with a local tokenizer.
            if len(proposed.research_context.encode("utf-8")) > 65536:
                return False
            try:
                self.gateway.check_input(proposed, model)
            except LLMError as error:
                if error.code not in ("CONTEXT_LIMIT", "REQUEST_TOO_LARGE"):
                    raise
                return False
            return self.gateway.input_tokens(proposed, model) - base_tokens <= capacity

        for fetched in documents:
            document = SourceDocument.model_validate_json(canonical_payload(fetched.document))
            if (
                document.source_id != fetched.selected.source.source_id
                or hashlib.sha256(document.text.encode()).hexdigest() != document.digest
            ):
                raise ValueError("Invalid document provenance")
            if document.digest in seen or len(document.text.strip()) < 64:
                continue
            seen.add(document.digest)

            def provenance(
                length: int,
                fetched: FetchedSource = fetched,
                document: SourceDocument = document,
            ) -> SourceProvenance:
                return SourceProvenance(
                    marker=f"R{len(sources) + 1}",
                    search_run_id=fetched.selected.search_run_id,
                    fetch_run_id=fetched.fetch_run_id,
                    source_id=document.source_id,
                    original_url=fetched.selected.source.url,
                    final_url=document.final_url,
                    title=fetched.selected.source.title,
                    fetched_at=document.fetched_at,
                    content_digest=document.digest,
                    excerpt=document.text[:length],
                    excerpt_start=0,
                    excerpt_end=length,
                )

            low, high, best = 64, min(8000, len(document.text)), 0
            # Bounded binary fit uses the gateway's actual counter, all system,
            # history, vision/PDF, request bytes, output and reasoning reserves.
            while low <= high:
                middle = (low + high) // 2
                if fits([*sources, provenance(middle)]):
                    best, low = middle, middle + 1
                else:
                    high = middle - 1
            if best:
                sources.append(provenance(best))
        if not sources:
            raise LLMError("RESEARCH_NO_SOURCES", 422)
        if len(sources) < len(documents):
            limitations.append("duplicate_short_or_over_budget_sources_omitted")
        # Account the final limitations too. If their overhead no longer fits,
        # fall back to the same bounded omission statement already counted.
        if not fits(sources):
            limitations = limitations[: 2 + int(unavailable) + int(partial_search)]
        result = grounded_request(request, sources, limitations)
        self.gateway.check_input(result, model)
        tokens = self.gateway.input_tokens(result, model) - base_tokens
        if tokens > capacity:
            raise LLMError("CONTEXT_LIMIT", 413)
        return GroundingContext(result, sources, tokens, limitations)


def assess_answer(text: str, sources: list[SourceProvenance]) -> GroundingAssessment:
    provided = {s.marker for s in sources}
    citations: list[CitationReference] = []
    unknown: list[str] = []
    truncated = False
    unknown_truncated = False
    # Only this internal marker grammar can ever become a citation. Bare URLs,
    # UUIDs and other model prose never create a source or evidence reference.
    for match in re.finditer(r"\[\[([^\[\]\n]{1,100})\]\]", text):
        marker = match.group(1)
        if marker in provided:
            if len(citations) < 256:
                citations.append(
                    CitationReference(marker=marker, start=match.start(), end=match.end())
                )
            else:
                truncated = True
        elif marker not in unknown:
            if len(unknown) < 32:
                unknown.append(marker)
            else:
                unknown_truncated = True
    return GroundingAssessment(
        claim_support="unverified" if sources else "missing",
        citations=citations,
        unknown_markers=unknown,
        citations_truncated=truncated,
        unknown_markers_truncated=unknown_truncated,
    )
