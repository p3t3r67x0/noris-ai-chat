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
    "TOOL_CANCELLED",
    "PROVIDER_RATE_LIMIT",
    "PROVIDER_ERROR",
    "PROVIDER_OUTCOME_UNKNOWN",
]


class ToolError(Exception):
    def __init__(self, code: ToolErrorCode) -> None:
        self.code: ToolErrorCode = code
        super().__init__(code)

    @property
    def status(self) -> int:
        return {
            "TOOL_UNAVAILABLE": 503,
            "TOOL_FORBIDDEN": 403,
            "TOOL_NOT_FOUND": 404,
            "TOOL_INPUT_INVALID": 422,
            "TOOL_OUTPUT_INVALID": 502,
            "BUDGET_LIMIT": 429,
            "PROVIDER_RATE_LIMIT": 429,
            "TOOL_TIMEOUT": 504,
            "PROVIDER_ERROR": 502,
            "PROVIDER_OUTCOME_UNKNOWN": 502,
        }.get(self.code, 409)

    @property
    def message(self) -> str:
        return {
            "TOOL_UNAVAILABLE": "Tool is unavailable",
            "TOOL_FORBIDDEN": "Tool permission denied",
            "TOOL_NOT_FOUND": "Tool resource not found",
            "TOOL_INPUT_INVALID": "Invalid tool input",
            "TOOL_OUTPUT_INVALID": "Invalid tool result",
            "BUDGET_LIMIT": "Tool budget exceeded",
            "APPROVAL_REQUIRED": "Tool approval required",
            "APPROVAL_EXPIRED": "Tool approval expired",
            "TOOL_TIMEOUT": "Tool deadline exceeded",
            "TOOL_CANCELLED": "Tool execution cancelled",
            "TOOL_INTERRUPTED": "Tool execution interrupted",
            "PROVIDER_RATE_LIMIT": "Tool provider rate limit exceeded",
            "PROVIDER_ERROR": "Tool provider request failed",
            "PROVIDER_OUTCOME_UNKNOWN": "Tool provider outcome is unknown",
        }.get(self.code, "Tool state conflicts with this request")
