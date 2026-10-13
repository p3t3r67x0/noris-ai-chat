"""Server-owned permissions and reviewed provider/cost snapshots; deny by default."""

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

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
