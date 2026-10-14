"""Deterministic relevance, rank, URL deduplication and hostname diversity."""

import re
from dataclasses import dataclass
from uuid import UUID

from noris_ai.tools.registry import canonical_payload
from noris_ai.tools.schemas import SearchResult, SearchSource, search_source_id


@dataclass(frozen=True)
class SavedSearch:
    run_id: UUID
    result: SearchResult


@dataclass(frozen=True)
class SelectedSource:
    search_run_id: UUID
    source: SearchSource


def select_sources(question: str, searches: list[SavedSearch], limit: int) -> list[SelectedSource]:
    if not 0 <= limit <= 3 or len(searches) > 3:
        raise ValueError("Selection limit exceeded")
    terms = {t.casefold() for t in re.findall(r"\w{3,}", question)}
    groups: list[list[SelectedSource]] = []
    seen_ids: set[UUID] = set()
    seen_urls: set[str] = set()
    for saved in searches:
        group: list[SelectedSource] = []
        result = SearchResult.model_validate_json(canonical_payload(saved.result))
        if len({s.source_id for s in result.sources}) != len(result.sources):
            raise ValueError("Duplicate source IDs")
        for source in result.sources:
            url = str(source.url)
            if source.source_id != search_source_id(result.config_version, url):
                raise ValueError("Invalid source identity")
            if source.source_id not in seen_ids and url not in seen_urls:
                group.append(SelectedSource(saved.run_id, source))
                seen_ids.add(source.source_id)
                seen_urls.add(url)
        groups.append(group)
    # Lexical overlap is a transparent tie breaker, never a quality/fact score.
    for group in groups:
        group.sort(
            key=lambda c: (
                not bool(
                    terms
                    & {
                        t.casefold()
                        for t in re.findall(r"\w{3,}", c.source.title + " " + c.source.snippet)
                    }
                )
            )
        )
    # Give later queries a bounded chance before consuming the fetch cap on the
    # first run. Hostname diversity still applies, without implying independence.
    candidates = [
        group[index]
        for index in range(max((len(group) for group in groups), default=0))
        for group in groups
        if index < len(group)
    ]
    selected: list[SelectedSource] = []
    hosts: set[str | None] = set()
    for candidate in candidates:
        if len(selected) == limit:
            break
        if candidate.source.url.host not in hosts:
            selected.append(candidate)
            hosts.add(candidate.source.url.host)
    for candidate in candidates:
        if len(selected) == limit:
            break
        if candidate not in selected:
            selected.append(candidate)
    return selected
