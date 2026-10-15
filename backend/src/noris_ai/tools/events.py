"""Public, bounded tool projections; no input, provider response or audit data."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from noris_ai.chat.schemas import JsonApiSchema
from noris_ai.tools.errors import ToolErrorCode
from noris_ai.tools.schemas import ApprovalState, Digest, ToolRunState

MAX_TOOL_EVENT_BYTES = 16_384
MAX_GENERATION_TOOL_RUNS = 128
TOOL_SNAPSHOT_PAGE_SIZE = 16
PublicToolId = Literal["web.search.v1", "web.fetch.v1"]
ToolEventType = Literal[
    "tool.started",
    "tool.progress",
    "tool.result",
    "tool.approval_required",
    "tool.completed",
    "tool.failed",
    "tool.cancelled",
    "tool.timed_out",
]


class ToolEventSchema(JsonApiSchema):
    model_config = JsonApiSchema.model_config | {
        "json_schema_serialization_defaults_required": True,
        "strict": True,
    }


class ToolApprovalProjection(ToolEventSchema):
    approvalId: UUID
    inputDigest: Digest
    state: ApprovalState
    expiresAt: AwareDatetime


class ToolResultReference(ToolEventSchema):
    resultVersion: Literal[1] = 1
    # Counts derive exclusively from output-schema validation. Content stays in REST.
    sourceCount: int | None = Field(default=None, ge=0, le=8)


class ToolProjection(ToolEventSchema):
    runId: UUID
    toolId: PublicToolId
    state: ToolRunState
    lastSequence: int = Field(ge=0)
    updatedAt: AwareDatetime
    cancelRequested: bool
    approval: ToolApprovalProjection | None = None
    result: ToolResultReference | None = None
    errorCode: ToolErrorCode | None = None

    @model_validator(mode="after")
    def consistent(self) -> ToolProjection:
        if (self.state == "succeeded") != (self.result is not None):
            raise ValueError("Result requires succeeded state")
        return self


class ToolEvent(ToolEventSchema):
    version: Literal[1] = 1
    eventVersion: Literal[1] = 1
    type: ToolEventType
    conversationId: UUID
    generationId: UUID
    runId: UUID
    seq: int = Field(ge=1)
    timestamp: AwareDatetime
    payload: ToolProjection

    @model_validator(mode="after")
    def consistent(self) -> ToolEvent:
        states: dict[str, tuple[str, ...]] = {
            "tool.started": ("running",),
            "tool.progress": ("queued", "running", "awaiting_approval"),
            "tool.result": ("succeeded",),
            "tool.approval_required": ("awaiting_approval",),
            "tool.completed": ("succeeded",),
            "tool.failed": ("failed", "interrupted", "outcome_unknown"),
            "tool.cancelled": ("cancelled",),
            "tool.timed_out": ("timed_out",),
        }
        if (
            self.payload.state not in states[self.type]
            or self.runId != self.payload.runId
            or self.seq != self.payload.lastSequence
            or self.timestamp != self.payload.updatedAt
            or (self.type == "tool.approval_required" and self.payload.approval is None)
        ):
            raise ValueError("Inconsistent tool event")
        if len(self.model_dump_json().encode()) > MAX_TOOL_EVENT_BYTES:
            raise ValueError("Tool event exceeds limit")
        return self


class ToolSnapshotEvent(ToolEventSchema):
    version: Literal[1] = 1
    eventVersion: Literal[1] = 1
    type: Literal["tool.snapshot"] = "tool.snapshot"
    conversationId: UUID
    generationId: UUID
    lastSequence: int = Field(ge=0)
    timestamp: AwareDatetime
    runs: list[ToolProjection] = Field(max_length=TOOL_SNAPSHOT_PAGE_SIZE)

    @model_validator(mode="after")
    def consistent(self) -> ToolSnapshotEvent:
        if any(run.lastSequence > self.lastSequence for run in self.runs):
            raise ValueError("Projection exceeds snapshot sequence")
        if len(self.model_dump_json().encode()) > MAX_TOOL_EVENT_BYTES:
            raise ValueError("Tool snapshot exceeds limit")
        return self
