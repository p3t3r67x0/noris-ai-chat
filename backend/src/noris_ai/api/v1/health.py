from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from noris_ai import __version__
from noris_ai.core.schemas import ErrorDetail, ErrorResponse, HealthResponse, ReadinessResponse
from noris_ai.db.readiness import ReadinessProbe

router = APIRouter(prefix="/health", tags=["Health"])


async def get_readiness_probe(request: Request) -> ReadinessProbe:
    return cast(ReadinessProbe, request.app.state.readiness_probe)


@router.get("/live", operation_id="getLiveness", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """Process health, independent of database availability."""
    return HealthResponse(version=__version__)


@router.get(
    "/ready",
    operation_id="getReadiness",
    response_model=ReadinessResponse,
    responses={503: {"model": ErrorResponse, "description": "Database or migrations unavailable"}},
)
async def readiness(
    request: Request, probe: Annotated[ReadinessProbe, Depends(get_readiness_probe)]
) -> ReadinessResponse | JSONResponse:
    """Ready only when PostgreSQL is reachable and the baseline is applied."""
    if await probe.is_ready():
        return ReadinessResponse()
    error = ErrorResponse(
        error=ErrorDetail(
            code="NOT_READY",
            message="Service dependencies are not ready",
            request_id=cast(UUID, request.state.request_id),
        )
    )
    return JSONResponse(status_code=503, content=error.model_dump(mode="json"))
