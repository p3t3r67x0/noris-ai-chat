"""Versioned public resource projections, excluding raw input and audit payloads."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from noris_ai.chat.schemas import JsonApiSchema
from noris_ai.core.schemas import ApiSchema
from noris_ai.tools.errors import ToolErrorCode
from noris_ai.tools.schemas import (
    ApprovalState,
    Digest,
    SearchResult,
    SourceDocument,
    ToolRunSnapshot,
)


class ToolCapability(ApiSchema):
    toolId: str
    status: Literal["available", "unavailable"]
    reasonCode: ToolErrorCode | None = None


class ToolCapabilitiesResponse(ApiSchema):
    schemaVersion: Literal[1] = 1
    features: list[ToolCapability]


class ToolApprovalDecision(JsonApiSchema):
    # Same JSON UUID parsing as existing chat REST requests. Tool payloads
    # continue to use strict JSON validation in the registry.
    requestId: UUID
    inputDigest: Digest
    decision: Literal["approve", "deny"]


class ToolApprovalResponse(ApiSchema):
    schemaVersion: Literal[1] = 1
    id: UUID
    runId: UUID
    inputDigest: Digest
    permissionScope: str
    provider: str
    configVersion: str
    maxCalls: int = Field(ge=1)
    maxCost: str
    currency: str
    state: ApprovalState
    expiresAt: AwareDatetime
    decidedAt: AwareDatetime | None


class ToolRunResponse(ApiSchema):
    schemaVersion: Literal[1] = 1
    run: ToolRunSnapshot
    errorCode: ToolErrorCode | None
    latestResult: SearchResult | SourceDocument | None
    approval: ToolApprovalResponse | None
