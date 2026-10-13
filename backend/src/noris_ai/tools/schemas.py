"""Bounded, versioned internal contracts. No public execute-by-name API."""

import unicodedata
from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, HttpUrl, field_validator

from noris_ai.core.schemas import ApiSchema
from noris_ai.tools.errors import ToolError

MAX_INPUT_BYTES = 65_536
MAX_OUTPUT_BYTES = 262_144
SEARCH_INPUT_BYTES = 4096
SEARCH_OUTPUT_BYTES = 65_536
InvocationKind = Literal["web_mode", "research_step", "user_action"]
ToolRunState = Literal[
    "queued",
    "awaiting_approval",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "timed_out",
    "interrupted",
    "outcome_unknown",
]
ApprovalState = Literal["pending", "approved", "denied", "expired"]
TERMINAL_STATES: frozenset[ToolRunState] = frozenset(
    {"succeeded", "failed", "cancelled", "timed_out", "interrupted", "outcome_unknown"}
)
TRANSITIONS: Mapping[ToolRunState, frozenset[ToolRunState]] = MappingProxyType(
    {
        "queued": frozenset(
            {"awaiting_approval", "running", "failed", "cancelled", "interrupted", "timed_out"}
        ),
        "awaiting_approval": frozenset(
            {"running", "failed", "cancelled", "interrupted", "timed_out"}
        ),
        "running": frozenset(TERMINAL_STATES),
    }
)
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ToolId = Annotated[
    str,
    Field(
        min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+\.v[1-9][0-9]*$"
    ),
]
StepKey = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.:-]+$")]
WarningText = Annotated[str, Field(min_length=1, max_length=200)]
SourceUrl = Annotated[HttpUrl, Field(max_length=2048)]


def check_transition(current: ToolRunState, target: ToolRunState) -> None:
    if target not in TRANSITIONS.get(current, frozenset()):
        raise ToolError("TOOL_STATE_CONFLICT")


class ToolSchema(ApiSchema):
    """Strict and frozen like the existing API schemas, but internal for P1a."""


class SearchInput(ToolSchema):
    query: str = Field(min_length=1, max_length=1000)
    language: Literal["de", "en"]
    time_range: Literal["day", "month", "year"] | None = None
    limit: int = Field(default=8, ge=1, le=8)

    @field_validator("query")
    @classmethod
    def valid_query(cls, value: str) -> str:
        if not value.strip() or any(unicodedata.category(c) in {"Cc", "Cs"} for c in value):
            raise ValueError("Invalid search query")
        return value


class SearchSource(ToolSchema):
    source_id: UUID
    title: str = Field(min_length=1, max_length=500)
    url: SourceUrl
    snippet: str = Field(max_length=4096)
    published_at: AwareDatetime | None = None


class SearchResult(ToolSchema):
    sources: list[SearchSource] = Field(max_length=8)
    warnings: list[WarningText] = Field(default_factory=list, max_length=10)
    provider: Literal["searxng", "brave"]
    config_version: str = Field(min_length=1, max_length=100)
    fetched_at: AwareDatetime
    partial: bool = False


class FetchInput(ToolSchema):
    # Only a saved source identifier, never a URL supplied by an LLM/client.
    source_id: UUID


class SourceDocument(ToolSchema):
    source_id: UUID
    text: str = Field(max_length=65_536)
    digest: Digest
    mime: Literal["text/plain", "text/html"]
    final_url: SourceUrl
    fetched_at: AwareDatetime


class ToolRunCreate(ToolSchema):
    """Trusted server context. Browser/LLM data only enters schema validation."""

    id: UUID
    conversation_id: UUID
    generation_id: UUID
    parent_run_id: UUID | None = None
    step_key: StepKey
    tool_id: ToolId
    invocation_kind: InvocationKind
    provider_key: str | None = Field(default=None, min_length=1, max_length=100)
    config_version: str | None = Field(default=None, min_length=1, max_length=100)
    deadline_at: AwareDatetime


class ToolRunSnapshot(ToolSchema):
    id: UUID
    conversation_id: UUID
    generation_id: UUID
    parent_run_id: UUID | None
    step_key: StepKey
    tool_id: ToolId
    schema_version: int = Field(ge=1)
    invocation_kind: InvocationKind
    input_digest: Digest
    state: ToolRunState
    attempt: int = Field(ge=1)
    deadline_at: datetime
    cancel_requested_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    execution_deadline_at: datetime | None = None
