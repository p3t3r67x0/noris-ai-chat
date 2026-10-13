"""Owner-scoped projections and decisions. There is intentionally no execute route."""

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Request

from noris_ai.api.v1.conversations import ERROR_RESPONSES, ChatAccess
from noris_ai.tools.api_schemas import (
    ToolApprovalDecision,
    ToolApprovalResponse,
    ToolCapabilitiesResponse,
    ToolCapability,
    ToolRunResponse,
)
from noris_ai.tools.errors import ToolError
from noris_ai.tools.runtime import ToolRuntime

router = APIRouter(prefix="/chat", tags=["Tools"])


def runtime(request: Request) -> ToolRuntime:
    return cast(ToolRuntime, request.app.state.tool_runtime)


@router.get(
    "/tools/capabilities",
    operation_id="getToolCapabilities",
    response_model=ToolCapabilitiesResponse,
    responses=ERROR_RESPONSES,
)
async def capabilities(request: Request, access: ChatAccess) -> ToolCapabilitiesResponse:
    del access  # Existing Basic/origin dependency identifies the single server owner.
    service = runtime(request)
    features: list[ToolCapability] = []
    for definition in service.registry.definitions:
        try:
            service.policy.require(service.registry.get(definition.name))
            features.append(ToolCapability(toolId=definition.name, status="available"))
        except ToolError as error:
            features.append(
                ToolCapability(toolId=definition.name, status="unavailable", reasonCode=error.code)
            )
    return ToolCapabilitiesResponse(features=features)


@router.get(
    "/tool-runs/{run_id}",
    operation_id="getToolRun",
    response_model=ToolRunResponse,
    responses=ERROR_RESPONSES,
)
async def get_run(run_id: UUID, request: Request, access: ChatAccess) -> ToolRunResponse:
    _, owner = access
    repository = runtime(request).repository
    return await repository.public_snapshot(owner, run_id)


@router.post(
    "/tool-approvals/{approval_id}/decision",
    operation_id="decideToolApproval",
    response_model=ToolApprovalResponse,
    responses=ERROR_RESPONSES,
)
async def decide(
    approval_id: UUID, payload: ToolApprovalDecision, request: Request, access: ChatAccess
) -> ToolApprovalResponse:
    _, owner = access
    repository = runtime(request).repository
    await repository.decide(
        owner,
        approval_id,
        payload.requestId,
        payload.inputDigest,
        payload.decision,
        policy=runtime(request).policy,
    )
    return await repository.public_approval(owner, approval_id)
