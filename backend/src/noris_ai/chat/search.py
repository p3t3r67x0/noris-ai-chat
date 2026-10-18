"""Bounded literal AND search. No stemming, SQL fragments or external index.

NFC + Unicode default casefold (PostgreSQL 18 PG_UNICODE_FAST, Unicode 16).
Terms are separated by Unicode White_Space; punctuation remains literal.
"""

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import String, and_, case, func, or_, select, union_all
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from noris_ai.chat.errors import ChatError

SPACE = re.compile(r"[\t\n\v\f\r \u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+")
MAX_TERMS = 32


def fold(value: str) -> str:
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", value).casefold())


def search_text(column: ColumnElement[str] | InstrumentedAttribute[str]) -> ColumnElement[str]:
    # Both index definitions and queries must use this exact immutable expression.
    unicode = func.normalize(
        func.casefold(func.normalize(column).collate("pg_unicode_fast")), type_=String
    ).collate("C")
    # In UTF8 equal byte/character lengths prove that every character is ASCII.
    # Its NFC/casefold is exactly C-locale lowercase; avoid two Unicode passes.
    return case(
        (func.char_length(column) == func.octet_length(column), func.lower(column.collate("C"))),
        else_=unicode,
    )


def pattern(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def plain_ascii(term: str) -> bool:
    # Canonical Unicode aliases exist for ';' and '`' (Greek punctuation).
    return term.isascii() and not any(c.isalpha() or c in ";`" for c in term)


def literal_match(
    column: ColumnElement[str] | InstrumentedAttribute[str], term: str
) -> ColumnElement[bool]:
    # These literals cannot be introduced by NFC/casefold. Compare them directly
    # to avoid normalizing every long response for '%' or '1'.
    value = column.collate("C") if plain_ascii(term) else search_text(column)
    return value.like(pattern(term), escape="\\")


@dataclass(frozen=True)
class SearchQuery:
    phrase: str
    terms: tuple[str, ...]

    @classmethod
    def parse(cls, value: str) -> SearchQuery:
        if len(value) > 200 or "\x00" in value:
            raise ChatError("INVALID_INPUT", 422)
        phrase = SPACE.sub(" ", fold(value)).strip(" ")
        terms = tuple(dict.fromkeys(phrase.split(" "))) if phrase else ()
        if len(terms) > MAX_TERMS:
            raise ChatError("INVALID_INPUT", 422)
        return cls(phrase, terms)

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.phrase.encode()).hexdigest()

    def condition(self, owner: UUID) -> ColumnElement[bool]:
        from noris_ai.chat.models import ChatConversation as C
        from noris_ai.chat.models import ChatMessage as M

        conditions: list[ColumnElement[bool]] = []
        for term in self.terms:
            # Independent terms may occur in different fields/messages/branches.
            # IN/UNION exposes the existing PostgreSQL trigram indexes to the planner.
            candidates = union_all(
                select(C.id).where(
                    C.owner_id == owner,
                    C.deleted_at.is_(None),
                    literal_match(C.title, term),
                ),
                select(M.conversation_id)
                .join(C, C.id == M.conversation_id)
                .where(
                    C.owner_id == owner,
                    C.deleted_at.is_(None),
                    M.role.in_(("user", "assistant")),
                    literal_match(M.content, term),
                ),
            )
            message_match = (
                select(M.id)
                .where(
                    M.conversation_id == C.id,
                    M.role.in_(("user", "assistant")),
                    literal_match(M.content, term),
                )
                .offset(0)
                .exists()
            )
            correlated = or_(literal_match(C.title, term), message_match)
            if plain_ascii(term):
                conditions.append(correlated)
                continue
            # A bounded, uncorrelated probe distinguishes frequent matches
            # from selective ones. OFFSET keeps the frequent-word branch a
            # local existence check, rather than hashing the entire corpus.
            probe = (
                select(M.conversation_id)
                .join(C, C.id == M.conversation_id)
                .where(
                    C.owner_id == owner,
                    C.deleted_at.is_(None),
                    M.role.in_(("user", "assistant")),
                    literal_match(M.content, term),
                )
                .limit(256)
                .correlate(None)
                .subquery()
            )
            strategy = (
                select(
                    case(
                        (func.count() == 0, 0),
                        (
                            and_(
                                func.count() == 256,
                                func.count(func.distinct(probe.c.conversation_id)) >= 16,
                            ),
                            2,
                        ),
                        else_=1,
                    )
                )
                .select_from(probe)
                .scalar_subquery()
            )
            conditions.append(
                case(
                    {0: literal_match(C.title, term), 2: correlated},
                    value=strategy,
                    else_=C.id.in_(candidates),
                )
            )
        return and_(*conditions)


def excerpt(content: str, query: SearchQuery) -> str:
    """NFC presentation, original case; map casefold expansions to source offsets."""
    from bisect import bisect_left, bisect_right

    content = unicodedata.normalize("NFC", content)
    normalized = fold(content)
    index = -1
    length = 0
    for needle in dict.fromkeys((query.phrase, *query.terms)):
        index = normalized.find(needle)
        if index >= 0:
            length = len(needle)
            break
    if index < 0:
        return content[:180]
    # Prefix lengths avoid a per-character allocation over every long response.
    positions = range(len(content) + 1)

    def size(offset: int) -> int:
        return len(fold(content[:offset]))

    first = max(0, bisect_right(positions, index, key=size) - 1)
    last = bisect_left(positions, index + length, key=size)
    while first > 0 and unicodedata.combining(content[first]):
        first -= 1
    while last < len(content) and unicodedata.combining(content[last]):
        last += 1
    start = max(0, first - 60)
    # Keep the entire match even if casefold expanded/contracted it.
    end = min(len(content), max(start + 180, last))
    return ("…" if start else "") + content[start:end] + ("…" if end < len(content) else "")
