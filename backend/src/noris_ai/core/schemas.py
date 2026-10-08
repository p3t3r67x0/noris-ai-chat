from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApiSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class HealthResponse(ApiSchema):
    status: Literal["ok"] = "ok"
    service: Literal["noris-ai"] = "noris-ai"
    version: str


class ReadinessResponse(ApiSchema):
    status: Literal["ready"] = "ready"


class ErrorDetail(ApiSchema):
    code: str
    message: str
    request_id: UUID


class ErrorResponse(ApiSchema):
    error: ErrorDetail
