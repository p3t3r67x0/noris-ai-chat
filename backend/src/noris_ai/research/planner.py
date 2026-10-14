"""Single bounded deterministic decision; no model output is executable."""

import re
from datetime import datetime
from typing import Literal

from noris_ai.research.schemas import ResearchPlan
from noris_ai.tools.schemas import SearchInput

CURRENT = re.compile(
    r"\b(neues|neuigkeiten|aktuell\w*|entwicklungen|förderprogramme|veranstaltungen|"
    r"angekündigt|version\w*|verändert|news|latest|current|released|release|events|"
    r"changed|announced|funding)\b",
    re.IGNORECASE,
)
EXPLICIT = re.compile(r"\b(recherchiere|recherche|quellen|websuche|research|sources)\b", re.I)
PRIVATE = re.compile(
    r"(@|https?://|\b(?:password|passwort|kennwort|zugangsschlüssel|zugangsdaten|"
    r"credential\w*|api[_ -]?(?:keys?|schlüssel|schluessel)|secret|geheim\w*|token|bearer|"
    r"systemprompt|system prompt|systemanweisungen|audit)\b|\b\d{7,}\b|"
    r"\b(?:sk-[\w-]+|gh[pousr]_[\w]+|AKIA[A-Z0-9]+)\b|-----BEGIN)",
    re.I,
)
QUERY_STOP_WORDS = frozenset(
    {
        "was",
        "gibt",
        "es",
        "bei",
        "hat",
        "sich",
        "welche",
        "welchen",
        "welcher",
        "für",
        "die",
        "der",
        "das",
        "ein",
        "eine",
        "einen",
        "und",
        "wurden",
        "im",
        "in",
        "von",
        "what",
        "is",
        "are",
        "the",
        "at",
        "has",
        "have",
        "which",
        "for",
        "about",
        "and",
        "recherchiere",
        "research",
        "bitte",
        "please",
        "quellen",
        "sources",
    }
)


def plan_research(
    question: str,
    language: Literal["de", "en"],
    deadline_at: datetime,
) -> ResearchPlan:
    # Validate before classification or shortening; never silently trim long inputs.
    SearchInput(query=question, language=language)
    if PRIVATE.search(question):
        raise ValueError("Question cannot be safely sent to search")
    intent = (
        "explicit_sources"
        if EXPLICIT.search(question)
        else "current_information"
        if CURRENT.search(question)
        else "not_required"
    )
    # Semicolon-separated topics permit at most three bounded searches. No history,
    # attachment text, model output or external metadata enters query construction.
    terms = list(dict.fromkeys(t.strip() for t in question.split(";") if t.strip()))
    return ResearchPlan(
        question=question,
        intent=intent,
        language=language,
        deadline_at=deadline_at,
        searches=[
            SearchInput(
                query=" ".join(
                    word
                    for word in re.findall(r"[\w.+#-]+", t)
                    if word.casefold() not in QUERY_STOP_WORDS
                ),
                language=language,
            )
            for t in terms
        ]
        if intent != "not_required"
        else [],
        max_fetches=3 if intent != "not_required" else 0,
        max_tool_calls=6 if intent != "not_required" else 0,
    )
