"""Fixed internal errors, without provider payloads or validation details."""

from typing import Literal

ToolErrorCode = Literal[
    "TOOL_UNAVAILABLE",
    "TOOL_FORBIDDEN",
    "TOOL_INPUT_INVALID",
    "TOOL_OUTPUT_INVALID",
    "TOOL_NOT_FOUND",
    "TOOL_CONFLICT",
    "TOOL_STATE_CONFLICT",
    "APPROVAL_REQUIRED",
    "APPROVAL_EXPIRED",
    "BUDGET_LIMIT",
    "TOOL_TIMEOUT",
    "TOOL_INTERRUPTED",
    "PROVIDER_RATE_LIMIT",
    "PROVIDER_ERROR",
    "PROVIDER_OUTCOME_UNKNOWN",
]


class ToolError(Exception):
    def __init__(self, code: ToolErrorCode) -> None:
        self.code = code
        super().__init__(code)
