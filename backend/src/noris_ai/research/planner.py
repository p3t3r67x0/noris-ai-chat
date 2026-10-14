"""Single bounded deterministic decision; no model output is executable."""

import re
from datetime import datetime
from typing import Literal

from noris_ai.research.schemas import ResearchPlan
from noris_ai.tools.schemas import SearchInput

CURRENT = re.compile(
    r"\b(neu(?:e[snrm]?)?|neuigkeiten|aktuell\w*|entwicklungen|förderprogramme|veranstaltungen|"
    r"angekündigt|version\w*|verändert|geändert|new|news|latest|current|released|release|events|"
    r"changed|announced|funding)\b",
    re.IGNORECASE,
)
EXPLICIT = re.compile(r"\b(recherchiere|recherche|quellen|websuche|research|sources)\b", re.I)
PRIVATE = re.compile(
    r"(@|https?://|\b(?:passwords?|passw(?:ort|örter|oerter)|kennw(?:ort|örter|oerter)|"
    r"zugangsschlüssel|zugangsdaten|credential\w*|api[_ -]?(?:keys?|schlüssel|schluessel)|"
    r"secrets?|geheim\w*|tokens?|bearer|systemprompts?|system prompts?|"
    r"systemanweisungen|audit)\b|\b\d{7,}\b|"
    r"\b(?:sk-[\w-]+|gh[pousr]_[\w]+|github_pat_[\w]+|AKIA[A-Z0-9]+)\b|"
    r"\beyJ[\w-]+\.[\w-]+\.[\w-]+\b|-----BEGIN)",
    re.I,
)
# Only these named technical topics can bypass the conservative keyword guard.
# Disclosure checks always inspect the original question first, not this masking.
TECHNICAL_TOKEN_TOPICS = re.compile(
    r"\b(?:api[- ]?)?tokens?[- ](?:limits?|budgets?)\b|"
    r"\b(?:oauth(?:2)?[- ]+)?access[- ]+tokens?\b"
    r"(?=\s*(?:$|[?.!,;]|(?:documentation|authentication|flow|flows|specification|"
    r"security|limits|budgets|for|in|of|about|and|und|für|work|function|"
    r"funktionieren|Dokumentation|Authentifizierung)\b))",
    re.I,
)
DISCLOSURE_LABEL = r"(?:api[-_ ]*|(?:oauth(?:2)?[-_ ]*)?(?:access|refresh|id|auth)[-_ ]*)?tokens?"
# A technical topic elsewhere must not hide credentials in common config/JSON
# field names, including camelCase and snake_case with a bounded prefix.
CREDENTIAL_LABEL = (
    r"(?:[a-z][a-z0-9_-]{0,63})?(?:passwords?|passwort|kennwort|secrets?|credentials?|"
    r"(?:api|private|secret)[-_ ]*keys?|access[-_ ]*keys?(?:[-_ ]*id)?|tokens?)"
)
DISCLOSURE_FIELDS = rf"(?:{DISCLOSURE_LABEL}|{CREDENTIAL_LABEL})"
PII_LABEL = (
    r"(?:telefon(?:nummer)?|handy(?:nummer)?|tel\.?|phone(?:[-_ ]*number)?|"
    r"adresse|wohnadresse|anschrift|address|geburtsdatum|date[-_ ]*of[-_ ]*birth|"
    r"kundennummer|vorname|nachname|name)"
)
OWNERSHIP = r"(?:my|our|mein(?:e|en|em|er|es)?|unser(?:e|en|em|er|es)?)"
MARKED_PRIVATE = re.compile(
    rf"\b{DISCLOSURE_FIELDS}(?:[- ](?:limits?|budgets?))?\b[\\\"'`*\u201d\u2019]*\s*(?:\]\s*)?"
    r"(?:[:=]|(?:ist|sind|lautet|lauten|is|are|value|wert)\b)\s*\S|"
    rf"\b{OWNERSHIP}\s+(?:(?:personal|private|persönlich\w*)\s+)?{DISCLOSURE_FIELDS}\b|"
    rf"\b{PII_LABEL}\b[\\\"'`*\u201d\u2019]*\s*(?:\]\s*)?"
    r"(?:[:=]|(?:ist|sind|lautet|lauten|is|are)\b)\s*\S|"
    rf"\b{OWNERSHIP}\s+{PII_LABEL}\b|"
    r"(?<!\w)(?:\+|00)\d{1,3}[ ()/.-]*(?:\d[ ()/.-]*){7,14}(?!\w)",
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
    if MARKED_PRIVATE.search(question) or PRIVATE.search(
        TECHNICAL_TOKEN_TOPICS.sub("technical topic", question)
    ):
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
    searches: dict[str, SearchInput] = {}
    if intent != "not_required":
        for term in terms:
            query = " ".join(
                word
                for word in re.findall(r"[\w.+#-]+", term)
                if word.casefold() not in QUERY_STOP_WORDS
            )
            # Dedupe after normalization too; repeated phrasing cannot abort a
            # valid plan or spend a second search reservation on the same terms.
            searches.setdefault(query.casefold(), SearchInput(query=query, language=language))
    return ResearchPlan(
        question=question,
        intent=intent,
        language=language,
        deadline_at=deadline_at,
        searches=list(searches.values()),
        max_fetches=3 if intent != "not_required" else 0,
        max_tool_calls=6 if intent != "not_required" else 0,
    )
