"""Owner-scoped projections and decisions. There is intentionally no execute route."""

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Request
from sqlalchemy import text

from noris_ai.api.v1.conversations import ERROR_RESPONSES, ChatAccess
from noris_ai.core.config import Settings
from noris_ai.research.reader import read_research
from noris_ai.research.schemas import ResearchCapability, ResearchView
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
    "/research/capability",
    operation_id="getResearchCapability",
    response_model=ResearchCapability,
    responses=ERROR_RESPONSES,
)
async def research_capability(request: Request, access: ChatAccess) -> ResearchCapability:
    del access
    config = cast(Settings, request.app.state.chat_settings)
    if not config.research_enabled:
        return ResearchCapability(available=False, reasonCode="RESEARCH_DISABLED")
    service = runtime(request)
    try:
        for tool_id in ("web.search.v1", "web.fetch.v1"):
            permission = service.policy.require(service.registry.get(tool_id))
            if permission.decision != "allow":
                return ResearchCapability(available=False, reasonCode="RESEARCH_APPROVAL_REQUIRED")
    except ToolError:
        return ResearchCapability(available=False, reasonCode="RESEARCH_UNAVAILABLE")
    return ResearchCapability(available=True)


@router.get(
    "/conversations/{conversation_id}/generations/{generation_id}/research",
    operation_id="getGenerationResearch",
    response_model=ResearchView | None,
    responses=ERROR_RESPONSES,
)
async def generation_research(
    conversation_id: UUID, generation_id: UUID, request: Request, access: ChatAccess
) -> ResearchView | None:
    service, owner = access
    async with service.repository.database() as session, session.begin():
        await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        return await read_research(
            session, runtime(request).repository, owner, conversation_id, generation_id
        )


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
    # Keep the existing public catalogue closed; consult the one runtime registry.
    for tool_id in ("web.search.v1", "web.fetch.v1"):
        try:
            service.policy.require(service.registry.get(tool_id))
            features.append(ToolCapability(toolId=tool_id, status="available"))
        except ToolError as error:
            features.append(
                ToolCapability(toolId=tool_id, status="unavailable", reasonCode=error.code)
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
