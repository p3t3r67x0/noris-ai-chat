"""Deterministic topic quality and original-input privacy regressions."""

from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from pydantic import ValidationError

from noris_ai.core.config import Settings
from noris_ai.llm.gateway import LLMGateway
from noris_ai.research.grounding import GroundingContextBuilder, assess_answer
from noris_ai.research.planner import plan_research
from noris_ai.research.selection import select_sources
from tests.unit.test_llm_api import FixtureProvider
from tests.unit.test_research import fetched, request, saved, source

DEADLINE = datetime.now(UTC) + timedelta(seconds=60)


@pytest.mark.parametrize(
    "question,language,topics,count",
    [
        ("Was gibt es Neues bei OpenStreetMap?", "de", ["OpenStreetMap"], 1),
        ("Welche aktuellen Entwicklungen gibt es bei QGIS?", "de", ["QGIS"], 1),
        ("Was hat sich bei PostgreSQL 18 verändert?", "de", ["PostgreSQL", "18"], 1),
        ("Was ist neu in PostGIS 3.6?", "de", ["PostGIS", "3.6"], 1),
        ("Welche Förderprogramme gibt es für Open Data?", "de", ["Open", "Data"], 1),
        ("What is new in PostgreSQL 18 and PostGIS?", "en", ["PostgreSQL", "PostGIS"], 1),
        (
            "Latest OpenStreetMap; current QGIS; PostgreSQL 18 release",
            "en",
            ["OpenStreetMap", "QGIS", "PostgreSQL"],
            3,
        ),
        (
            "Aktuelle QGIS-Version; PostGIS verändert; Open Data Förderprogramme",
            "de",
            ["QGIS", "PostGIS", "Open Data"],
            3,
        ),
        (
            "Compare current OpenStreetMap, QGIS, PostgreSQL, PostGIS and Open Data developments",
            "en",
            ["OpenStreetMap", "QGIS", "PostgreSQL", "PostGIS", "Open Data"],
            1,
        ),
        ("Und was hat sich beim Routing geändert?", "de", ["Routing"], 1),
        ("And what are the latest PostGIS developments?", "en", ["PostGIS"], 1),
    ],
)
def test_named_topics_survive_bounded_query_planning(
    question: str, language: Literal["de", "en"], topics: list[str], count: int
):
    plan = plan_research(question, language, DEADLINE)
    assert len(plan.searches) == count
    queries = " ".join(search.query for search in plan.searches)
    assert all(topic in queries for topic in topics)
    assert all(search.language == language and search.limit <= 8 for search in plan.searches)
    assert plan.max_tool_calls == 6 and plan.max_fetches == 3


@pytest.mark.parametrize(
    "question",
    [
        "Recherchiere Token-Limits von GPT-OSS",
        "Recherchiere API-Token-Budgets",
        "Research OAuth Access Tokens",
        "Research OAuth Access Token",
        "Latest token budgets",
        "Research GitHub API authentication documentation",
    ],
)
def test_technical_token_topics_are_data_not_credentials(question: str):
    plan = plan_research(question, "en", DEADLINE)
    assert len(plan.searches) == 1
    assert "technical topic" not in plan.searches[0].query


@pytest.mark.parametrize(
    "private",
    [
        "mein Token lautet fixture-only-abc",
        "Meine OAuth Access Tokens lauten fixture-only-abc",
        "OAuth Access Tokens: fixture-only-abc",
        "Meine API Tokens sind fixture-only-abc",
        "refresh_tokens=fixture-only-abc",
        "client_secret=fixture_only_abc",
        "clientSecret=fixture_only_abc",
        "dbPassword=fixture_only_abc",
        "my_password=fixture_only_abc",
        '{"client_secret":"fixture_only_abc"}',
        r"{\"clientSecret\":\"fixture_only_abc\"}",
        "`dbPassword`=fixture_only_abc",
        "**my_password**: fixture_only_abc",
        "app_private_key=fixture_only_abc",
        "clientAuthToken=fixture_only_abc",
        "AWS_SECRET_ACCESS_KEY=fixture_only_abc",
        "awsSecretAccessKey=fixture_only_abc",
        "aws_access_key_id=fixture_only_abc",
        "awsAccessKeyId=fixture_only_abc",
        "myToken=fixture_only_abc",
        'config["clientSecret"] = fixture_only_abc',
        "config['dbPassword'] = fixture_only_abc",
        'config["dateOfBirth"] = "01.01.1990"',
        "access_token = fixture-only-abc",
        "accessToken: fixture-only-abc",
        "OAuthAccessTokens=fixture-only-abc",
        '{"access_token": "fixture-only-abc"}',
        r"{\"access_token\": \"fixture-only-abc\"}",
        "`access_token` = fixture-only-abc",
        "**access_token**: fixture-only-abc",
        "“access_token”: fixture-only-abc",
        '{"OAuth Access Tokens": "fixture-only-abc"}',
        '"OAuth Access Token" = "fixture-only-abc"',
        "OAuth Access Token fixture-only-abc",
        "API-Token-Budgets=fixture-only-abc",
        "my personal access token fixture-only-abc",
        "Bearer: fixture-only-abc",
        "api_key=fixture-only-abc",
        "API-Schlüssel: fixture-only-abc",
        "Meine Passwörter sind fixture-only-abc",
        "my passwords are fixture-only-abc",
        "Kennwoerter: fixture-only-abc",
        "secrets=fixture-only-abc",
        "sk-fixture-only-abc",
        "ghp_fixture_only_abc",
        "github_pat_fixture_only_abc",
        "eyJfixture.payload.signature",
        "Meine Telefonnummer ist +49 (170) 123-45-67",
        "Tel. +49 170 12 34 56",
        "Meine Telefonnummer 0170 123 45 67",
        "Meine Kundennummer ist AB-12-CD",
        "Meine Wohnadresse ist Musterstraße 12, 12345 Musterstadt",
        "Mein Nachname ist Mustermann",
        "dateOfBirth=01.01.1990",
        '{"dateOfBirth":"01.01.1990"}',
        '{"phoneNumber":"0170 123 45 67"}',
        "fixture@example.org",
        "https://example.org/private",
    ],
)
def test_original_private_data_rejected_even_alongside_allowed_topics(private: str):
    with pytest.raises(ValueError):
        plan_research("Latest Token-Limits von GPT-OSS; " + private, "de", DEADLINE)


@pytest.mark.parametrize(
    "question",
    [
        "Und bei PostGIS?",
        "And what about the other one?",
        "Was ist zwei plus zwei?",
        "Wie geht es dir?",
    ],
)
def test_ambiguous_followups_do_not_invent_context_or_search_authority(question: str):
    plan = plan_research(question, "de", DEADLINE)
    assert plan.intent == "not_required"
    assert plan.searches == [] and plan.max_fetches == 0 and plan.max_tool_calls == 0


def test_normalized_equivalent_topics_use_one_search_and_preserve_plan_strictness():
    plan = plan_research("Latest QGIS; What is latest QGIS; latest QGIS", "en", DEADLINE)
    assert len(plan.searches) == 1
    assert plan.searches[0].query == "Latest QGIS"
    with pytest.raises(ValidationError):
        type(plan).model_validate({**plan.model_dump(), "searches": plan.searches * 2})


def test_complexity_never_expands_search_or_fetch_caps():
    with pytest.raises(ValidationError):
        plan_research(
            "Latest QGIS; latest PostgreSQL; latest PostGIS; latest OpenStreetMap", "en", DEADLINE
        )


def test_multi_topic_selection_does_not_spend_all_fetches_on_first_search():
    runs = [
        saved(
            [
                source(f"https://{topic.lower()}-{index}.example.org/release", f"Latest {topic}")
                for index in range(3)
            ]
        )
        for topic in ("QGIS", "PostgreSQL", "PostGIS")
    ]
    selected = select_sources("Latest QGIS; latest PostgreSQL; latest PostGIS", runs, 3)
    assert {value.search_run_id for value in selected} == {run.run_id for run in runs}
    assert len({value.source.url.host for value in selected}) == 3


async def test_document_existence_and_prepared_context_never_verify_a_claim(llm_config: Settings):
    gateway = LLMGateway(llm_config, FixtureProvider())
    base = request()
    model, capacity = await gateway.research_capacity(base)
    first = fetched()
    duplicate = fetched(first.document.text, "https://mirror.example.org/")
    context = GroundingContextBuilder(gateway).build(base, model, capacity, [first, duplicate])
    assert duplicate.document.source_id != first.document.source_id
    assert len(context.sources) == 1  # Both documents exist; only this excerpt is prepared.
    assessment = assess_answer(
        f"A claim [[R1]]. Mirror [[R2]]. Invented [[{duplicate.document.source_id}]].",
        context.sources,
    )
    assert [value.marker for value in assessment.citations] == ["R1"]
    assert assessment.unknown_markers == ["R2", str(duplicate.document.source_id)]
    assert assessment.claim_support == "unverified"
    assert assessment.citations[0].claim_support == "unverified"


def test_unknown_marker_overflow_is_bounded_and_explicit():
    assessment = assess_answer(" ".join(f"[[unknown_{index:02}]]" for index in range(33)), [])
    assert len(assessment.unknown_markers) == 32
    assert assessment.unknown_markers_truncated
    assert assessment.citations == [] and assessment.claim_support == "missing"
    assert not assess_answer("[[unknown]] " * 33, []).unknown_markers_truncated
