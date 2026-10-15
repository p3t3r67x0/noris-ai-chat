"""Server-owned permissions and reviewed provider/cost snapshots; deny by default."""

import re
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Literal

from pydantic import Field, field_validator

from noris_ai.core.schemas import ApiSchema
from noris_ai.tools.budget import DIMENSIONS, BudgetAmount
from noris_ai.tools.errors import ToolError
from noris_ai.tools.models import ToolRun
from noris_ai.tools.registry import RegisteredTool


@dataclass(frozen=True)
class ToolPermission:
    provider_key: str
    config_version: str
    decision: Literal["allow", "approval_required", "deny"]
    per_call: BudgetAmount
    daily_limit: BudgetAmount
    generation_limit: BudgetAmount
    currency: str = "USD"

    def __post_init__(self) -> None:
        if (
            not self.provider_key
            or not self.config_version
            or self.per_call.calls != 1
            or not self.per_call.fits(self.daily_limit)
            or not self.per_call.fits(self.generation_limit)
            or re.fullmatch(r"[A-Z]{3}", self.currency) is None
        ):
            raise ValueError("Invalid tool permission")

    def snapshot(self, permission: str) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "permission": permission,
            "decision": self.decision,
            "currency": self.currency,
            "maxCost": str(self.per_call.cost),
            "maxCalls": self.per_call.calls,
            "maxTokens": self.per_call.tokens,
            "maxBytes": self.per_call.bytes,
            "dailyLimits": {k: str(getattr(self.daily_limit, k)) for k in DIMENSIONS},
            "generationLimits": {k: str(getattr(self.generation_limit, k)) for k in DIMENSIONS},
        }


class ToolPolicy:
    def __init__(self, permissions: dict[str, ToolPermission] | None = None) -> None:
        self.permissions = MappingProxyType(dict(permissions or {}))

    @classmethod
    def from_operator_json(cls, payload: str | None) -> ToolPolicy:
        """Explicit server configuration, never a browser/LLM permission path."""
        if not payload:
            return cls()
        if len(payload.encode("utf-8")) > 16_384:
            raise ValueError("Operator permission config exceeds limit")
        config = OperatorPermissions.model_validate_json(payload)
        permissions: dict[str, ToolPermission] = {}
        for name, provider, value in (
            ("web.search.v1", "searxng", config.web_search),
            ("web.fetch.v1", "public_source", config.web_fetch),
        ):
            if value is not None:
                permissions[name] = ToolPermission(
                    provider_key=provider,
                    config_version=value.config_version,
                    decision=value.decision,
                    per_call=value.per_call.amount(),
                    daily_limit=value.daily_limit.amount(),
                    generation_limit=value.generation_limit.amount(),
                    currency=value.currency,
                )
        return cls(permissions)

    def require(self, definition: RegisteredTool, run: ToolRun | None = None) -> ToolPermission:
        if (
            definition.handler is None
            or definition.provider_key is None
            or definition.cost_policy != "bounded"
        ):
            raise ToolError("TOOL_UNAVAILABLE")
        permission = self.permissions.get(definition.name)
        if permission is None:
            raise ToolError("TOOL_UNAVAILABLE")
        if permission.decision == "deny":
            raise ToolError("TOOL_FORBIDDEN")
        if permission.provider_key != definition.provider_key:
            raise ToolError("TOOL_UNAVAILABLE")
        if run is not None and (
            run.provider_key != permission.provider_key
            or run.config_version != permission.config_version
            or run.schema_version != definition.schema_version
            or run.invocation_kind not in definition.allowed_invocation_kinds
        ):
            raise ToolError("TOOL_FORBIDDEN")
        return permission


class OperatorBudget(ApiSchema):
    calls: int = Field(ge=0, le=1_000_000)
    bytes: int = Field(ge=0, le=1_000_000_000_000)
    tokens: int = Field(default=0, ge=0, le=1_000_000_000)
    cost: Decimal = Field(default=Decimal(0), ge=0, le=1_000_000_000)

    def amount(self) -> BudgetAmount:
        return BudgetAmount(calls=self.calls, bytes=self.bytes, tokens=self.tokens, cost=self.cost)


class OperatorPermission(ApiSchema):
    # No default allow, config version, network destination or budget.
    decision: Literal["allow", "approval_required", "deny"]
    config_version: str = Field(min_length=1, max_length=100)
    currency: Literal["USD"] = "USD"
    per_call: OperatorBudget
    daily_limit: OperatorBudget
    generation_limit: OperatorBudget


class OperatorPermissions(ApiSchema):
    version: Literal[1]
    web_search: OperatorPermission | None = None
    web_fetch: OperatorPermission | None = None

    @field_validator("version", mode="before")
    @classmethod
    def integer_version(cls, value: object) -> object:
        if type(value) is not int or value != 1:
            raise ValueError("Unsupported permission config version")
        return value
