import json
from dataclasses import FrozenInstanceError, replace
from typing import cast
from uuid import uuid4

import pytest
from pydantic import ConfigDict

from noris_ai.tools.errors import ToolError
from noris_ai.tools.registry import (
    RetryPolicy,
    TimeoutPolicy,
    ToolRegistry,
    canonical_payload,
    create_tool_registry,
    payload_digest,
)
from noris_ai.tools.schemas import (
    TERMINAL_STATES,
    InvocationKind,
    SearchInput,
    ToolRunState,
    check_transition,
)


def test_fixed_registry_is_inert_and_unique() -> None:
    registry = create_tool_registry()
    assert {d.name for d in registry.definitions} == {"web.search.v1", "web.fetch.v1"}
    assert all(
        d.handler is None and d.provider_key is None and d.cost_policy == "disabled"
        for d in registry.definitions
    )
    with pytest.raises(ValueError, match="Duplicate tool ID"):
        ToolRegistry([registry.definitions[0], registry.definitions[0]])
    with pytest.raises(FrozenInstanceError):
        registry.definitions[0].name = "shell.exec.v1"  # type: ignore[misc]


@pytest.mark.parametrize(
    "name", ["web.search", "Web.search.v1", "shell", "https://host", "web.search.v2"]
)
def test_definition_ids_are_versioned_and_exact(name: str) -> None:
    with pytest.raises(ValueError):
        replace(create_tool_registry().definitions[0], name=name)


@pytest.mark.parametrize("name", ["shell.exec.v1", "web.search.v2", "https://host", "__import__"])
def test_unknown_tool_cannot_be_resolved(name: str) -> None:
    with pytest.raises(ToolError, match="TOOL_UNAVAILABLE"):
        create_tool_registry().get(name)


@pytest.mark.parametrize("kind", ["llm", "user_action", "provider", "shell"])
def test_unauthorized_invocation_rejected(kind: str) -> None:
    with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
        create_tool_registry().get("web.search.v1").validate_input(
            b'{"query":"test","language":"de"}',
            cast(InvocationKind, kind),
        )


@pytest.mark.parametrize(
    "payload",
    [
        b'{"query":"x","language":"de","provider":"evil"}',
        b'{"query":"x","language":"de","limit":"8"}',
        b'{"query":"x","language":"de","limit":true}',
        b'{"query":"x","language":"de","limit":9}',
        b'{"query":"x","language":"de","limit":0}',
        b'{"query":"x","language":"fr"}',
        b'{"query":"x","language":"de","language":"en"}',
        b'{"query":"   ","language":"de"}',
        b'{"query":"x\\u0000","language":"de"}',
        b"[]",
        b"{",
        b"\xff",
        b" " * 4097,
    ],
)
def test_input_is_strict_closed_and_byte_bounded(payload: bytes) -> None:
    with pytest.raises(ToolError, match="TOOL_INPUT_INVALID") as error:
        create_tool_registry().get("web.search.v1").validate_input(payload, "web_mode")
    assert str(error.value) == "TOOL_INPUT_INVALID"


def test_fetch_accepts_only_source_id() -> None:
    definition = create_tool_registry().get("web.fetch.v1")
    source = uuid4()
    parsed = definition.validate_input(json.dumps({"source_id": str(source)}).encode(), "web_mode")
    assert parsed.source_id == source
    with pytest.raises(ToolError, match="TOOL_INPUT_INVALID"):
        definition.validate_input(b'{"url":"https://example.org"}', "web_mode")


def test_output_is_validated_before_success() -> None:
    definition = create_tool_registry().get("web.search.v1")
    for payload in (b"{}", b'{"sources":[],"token":"secret"}', b" " * 65_537):
        with pytest.raises(ToolError, match="TOOL_OUTPUT_INVALID"):
            definition.validate_output(payload)


def test_schema_cannot_relax_existing_strict_contract() -> None:
    class PermissiveInput(SearchInput):
        model_config = ConfigDict(extra="allow", strict=False)

    with pytest.raises(ValueError, match="strict, closed and frozen"):
        replace(create_tool_registry().definitions[0], input_type=PermissiveInput)


def test_registration_cannot_be_changed_through_the_source_collection() -> None:
    definitions = list(create_tool_registry().definitions)
    registry = ToolRegistry(definitions)
    definitions.clear()
    assert len(registry.definitions) == 2
    with pytest.raises(ValueError, match="immutable"):
        replace(
            registry.definitions[0],
            allowed_invocation_kinds=cast(frozenset[InvocationKind], {"web_mode"}),
        )


def test_idempotency_digest_uses_validated_normalized_input() -> None:
    definition = create_tool_registry().get("web.search.v1")
    first = definition.validate_input(b'{"query":"x","language":"de"}', "web_mode")
    repeated = definition.validate_input(
        b'{"limit":8,"time_range":null,"language":"de","query":"x"}', "web_mode"
    )
    changed = definition.validate_input(b'{"query":"y","language":"de"}', "web_mode")
    assert payload_digest(canonical_payload(first)) == payload_digest(canonical_payload(repeated))
    assert payload_digest(canonical_payload(first)) != payload_digest(canonical_payload(changed))


@pytest.mark.parametrize("state", sorted(TERMINAL_STATES))
def test_terminal_states_cannot_restart(state: ToolRunState) -> None:
    with pytest.raises(ToolError, match="TOOL_STATE_CONFLICT"):
        check_transition(state, "running")


def test_queued_success_and_repeated_state_are_invalid() -> None:
    check_transition("queued", "awaiting_approval")
    check_transition("awaiting_approval", "running")
    check_transition("running", "succeeded")
    for target in ("succeeded", "queued"):
        with pytest.raises(ToolError, match="TOOL_STATE_CONFLICT"):
            check_transition("queued", cast(ToolRunState, target))


def test_invalid_timeout_and_unsafe_retries_rejected() -> None:
    for seconds in (0, -1, 601, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            TimeoutPolicy(total_seconds=seconds)
    for retries, idempotent in ((2, True), (1, False), (-1, True)):
        with pytest.raises(ValueError):
            RetryPolicy(max_retries=retries, idempotent=idempotent)
