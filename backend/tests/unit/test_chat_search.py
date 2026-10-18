"""Literal, deterministic search semantics and bound SQL; no database required."""

import uuid

import pytest
from sqlalchemy import select

from noris_ai.chat.errors import ChatError
from noris_ai.chat.models import ChatConversation
from noris_ai.chat.search import SearchQuery, excerpt, fold, pattern
from scripts.benchmark_chat_search import require_benchmark_database


@pytest.mark.parametrize(
    ("query", "phrase", "terms"),
    [
        (" Docker\tHEALTHCHECK  ", "docker healthcheck", ("docker", "healthcheck")),
        ("Äpfel A\u0308PFEL", "äpfel äpfel", ("äpfel",)),
        ("Straße STRASSE", "strasse strasse", ("strasse",)),
        ("Σ ς \u03c3", "\u03c3 \u03c3 \u03c3", ("\u03c3",)),
        ("東京\u3000健康", "東京 健康", ("東京", "健康")),
        ("e\u0301", "é", ("é",)),
        ("\u1100\u1161", "가", ("가",)),
        ("v0.12.3 %_ \\", "v0.12.3 %_ \\", ("v0.12.3", "%_", "\\")),
        ("\u0085\u00a0\u2003", "", ()),
    ],
)
def test_query_semantics(query: str, phrase: str, terms: tuple[str, ...]) -> None:
    parsed = SearchQuery.parse(query)
    assert (parsed.phrase, parsed.terms) == (phrase, terms)
    assert fold("é") != fold("e")
    assert fold("İ") != fold("i")


@pytest.mark.parametrize("value", ["x" * 201, "\x00", " ".join(str(i) for i in range(33))])
def test_query_limits(value: str) -> None:
    with pytest.raises(ChatError) as error:
        SearchQuery.parse(value)
    assert error.value.status == 422


def test_query_is_parameterized_and_like_metacharacters_are_literal() -> None:
    value = "%' OR true;--"
    statement = select(ChatConversation.id).where(
        SearchQuery.parse(value).condition(uuid.UUID(int=42))
    )
    compiled = statement.compile()
    assert value not in str(compiled)
    assert "true;--" not in str(compiled)
    assert any("true;--" in str(value) for value in compiled.params.values())
    assert pattern("a%_\\b") == "%a\\%\\_\\\\b%"


@pytest.mark.parametrize(
    ("content", "query", "expected"),
    [
        ("Straße", "STRASSE", "Straße"),
        ("A\u0308pfel", "äpfel", "Äpfel"),
        ("ΟΣΟΣ", "οσος", "ΟΣΟΣ"),
        ("\u1100\u1161", "가", "가"),
        ("İstanbul", "i", "İstanbul"),
    ],
)
def test_excerpt_preserves_case_and_contains_normalized_target(
    content: str, query: str, expected: str
) -> None:
    result = excerpt("x" * 300 + content + " tail", SearchQuery.parse(query))
    assert expected in result
    assert result.startswith("…")
    assert len(result) < 220


def test_excerpt_prefers_whole_phrase_over_earlier_individual_terms() -> None:
    content = "Docker " + "x" * 300 + "docker healthcheck " + "z" * 300
    result = excerpt(content, SearchQuery.parse("Docker healthcheck"))
    assert "docker healthcheck" in result
    assert result.startswith("…") and result.endswith("…")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://127.0.0.1/application",
        "postgresql+psycopg://127.0.0.1/noris_other_test",
        "postgresql+psycopg://remote.example/noris_search_benchmark_local_test",
    ],
)
def test_benchmark_refuses_application_or_remote_databases(url: str) -> None:
    with pytest.raises(ValueError, match="dedicated loopback"):
        require_benchmark_database(url)
