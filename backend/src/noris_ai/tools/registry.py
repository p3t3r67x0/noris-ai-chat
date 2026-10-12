"""Immutable startup registry, independent of providers and execution policy."""

import hashlib
import json
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal

from pydantic import TypeAdapter, ValidationError

from noris_ai.tools.errors import ToolError
from noris_ai.tools.schemas import (
    MAX_INPUT_BYTES,
    MAX_OUTPUT_BYTES,
    FetchInput,
    InvocationKind,
    SearchInput,
    SearchResult,
    SourceDocument,
    ToolId,
    ToolRunCreate,
    ToolSchema,
)


@dataclass(frozen=True)
class TimeoutPolicy:
    total_seconds: float = 15

    def __post_init__(self) -> None:
        if not 0 < self.total_seconds <= 600:
            raise ValueError("Invalid tool timeout")


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 0
    idempotent: bool = False

    def __post_init__(self) -> None:
        if self.max_retries not in (0, 1) or (self.max_retries and not self.idempotent):
            raise ValueError("Retries require an idempotent operation")


@dataclass(frozen=True)
class ToolDefinition[InputT: ToolSchema, OutputT: ToolSchema]:
    name: str
    schema_version: int
    input_type: type[InputT]
    output_type: type[OutputT]
    permission: Literal["web_search", "web_fetch", "library_attach", "image_generate"]
    allowed_invocation_kinds: frozenset[InvocationKind]
    provider_key: str | None = None
    # P1b supplies the full runtime context and dispatcher. No production handler in P1a.
    handler: Callable[[ToolRunCreate, InputT], Awaitable[OutputT]] | None = None
    timeout_policy: TimeoutPolicy = TimeoutPolicy()
    retry_policy: RetryPolicy = RetryPolicy()
    cost_policy: Literal["disabled", "bounded"] = "disabled"
    max_input_bytes: int = MAX_INPUT_BYTES
    max_output_bytes: int = MAX_OUTPUT_BYTES

    def __post_init__(self) -> None:
        TypeAdapter(ToolId).validate_python(self.name)
        if self.schema_version < 1 or not self.name.endswith(f".v{self.schema_version}"):
            raise ValueError("Tool ID and schema version must agree")
        if type(self.allowed_invocation_kinds) is not frozenset:
            raise ValueError("Invocation kinds must be immutable")
        if not self.allowed_invocation_kinds or not self.allowed_invocation_kinds <= {
            "web_mode",
            "research_step",
            "user_action",
        }:
            raise ValueError("Invalid invocation kinds")
        if not 0 < self.max_input_bytes <= MAX_INPUT_BYTES:
            raise ValueError("Invalid input limit")
        if not 0 < self.max_output_bytes <= MAX_OUTPUT_BYTES:
            raise ValueError("Invalid output limit")
        for schema in (self.input_type, self.output_type):
            if any(
                schema.model_config.get(key) != expected
                for key, expected in (("strict", True), ("extra", "forbid"), ("frozen", True))
            ):
                raise ValueError("Tool schemas must be strict, closed and frozen")

    def validate_input(self, payload: bytes, kind: InvocationKind) -> InputT:
        if kind not in self.allowed_invocation_kinds:
            raise ToolError("TOOL_FORBIDDEN")
        return validate_payload(self.input_type, payload, self.max_input_bytes, output=False)

    def validate_output(self, payload: bytes) -> OutputT:
        return validate_payload(self.output_type, payload, self.max_output_bytes, output=True)


def unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def validate_payload[InputT: ToolSchema](
    schema: type[InputT],
    payload: bytes,
    limit: int,
    *,
    output: bool,
) -> InputT:
    code = "TOOL_OUTPUT_INVALID" if output else "TOOL_INPUT_INVALID"
    if len(payload) > limit:
        raise ToolError(code)
    try:
        json.loads(payload, object_pairs_hook=unique_keys)
        return schema.model_validate_json(payload)
    except (ValidationError, ValueError, RecursionError) as exc:
        raise ToolError(code) from exc


def canonical_payload(value: ToolSchema) -> bytes:
    return json.dumps(
        value.model_dump(mode="json"),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def payload_digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


# Explicit erasure at the heterogeneous registry boundary; each definition retains its types.
RegisteredTool = ToolDefinition[Any, Any]


class ToolRegistry:
    def __init__(self, definitions: Iterable[RegisteredTool]) -> None:
        entries: dict[str, RegisteredTool] = {}
        for definition in definitions:
            if definition.name in entries:
                raise ValueError(f"Duplicate tool ID: {definition.name}")
            entries[definition.name] = definition
        self._definitions: Mapping[str, RegisteredTool] = MappingProxyType(entries)

    @property
    def definitions(self) -> tuple[RegisteredTool, ...]:
        return tuple(self._definitions.values())

    def get(self, tool_id: str) -> RegisteredTool:
        definition = self._definitions.get(tool_id)
        if definition is None:
            raise ToolError("TOOL_UNAVAILABLE")
        return definition


def create_tool_registry() -> ToolRegistry:
    """Fixed contracts only. Neither a provider nor an executable handler is enabled."""
    return ToolRegistry(
        (
            ToolDefinition(
                name="web.search.v1",
                schema_version=1,
                input_type=SearchInput,
                output_type=SearchResult,
                permission="web_search",
                allowed_invocation_kinds=frozenset({"web_mode", "research_step"}),
                max_input_bytes=4096,
                max_output_bytes=65_536,
            ),
            ToolDefinition(
                name="web.fetch.v1",
                schema_version=1,
                input_type=FetchInput,
                output_type=SourceDocument,
                permission="web_fetch",
                allowed_invocation_kinds=frozenset({"web_mode", "research_step"}),
                timeout_policy=TimeoutPolicy(total_seconds=10),
                max_input_bytes=256,
            ),
        )
    )
