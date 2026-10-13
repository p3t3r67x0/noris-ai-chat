"""Public event contract and forbidden data boundaries."""

# pyright: reportPrivateUsage=false

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from noris_ai.chat.generation import Peer
from noris_ai.core.config import Settings
from noris_ai.tools.events import ToolEvent, ToolProjection, ToolSnapshotEvent
from tests.unit.test_auto_continuation import Segments, worker


def event() -> dict[str, object]:
    run = uuid4()
    now = datetime.now(UTC)
    return ToolEvent(
        type="tool.started",
        conversationId=uuid4(),
        generationId=uuid4(),
        runId=run,
        seq=1,
        timestamp=now,
        payload=ToolProjection(
            runId=run,
            toolId="web.search.v1",
            state="running",
            lastSequence=1,
            updatedAt=now,
            cancelRequested=False,
        ),
    ).model_dump(mode="json")


def test_versioned_strict_json_roundtrip() -> None:
    value = event()
    assert ToolEvent.model_validate_json(json.dumps(value)).model_dump(mode="json") == value
    assert value["version"] == value["eventVersion"] == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", 2),
        ("eventVersion", 2),
        ("type", "tool.execute"),
        ("seq", 0),
        ("seq", "1"),
        ("seq", True),
        ("timestamp", "2026-10-13T10:00:00"),
        ("runId", str(uuid4())),
        ("input", "secret"),
        ("audit", {}),
    ],
)
def test_invalid_envelope(field: str, value: object) -> None:
    payload = event() | {field: value}
    with pytest.raises(ValidationError):
        ToolEvent.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    "field,value",
    [
        ("toolId", "unknown.tool.v1"),
        ("input", "secret"),
        ("output", {}),
        ("lastSequence", 2),
        ("state", "queued"),
        ("result", {"sourceCount": 9}),
        ("errorCode", "private provider body"),
        ("cancelRequested", "false"),
        ("secret", "x" * 20_000),
    ],
)
def test_invalid_projection(field: str, value: object) -> None:
    payload = event()
    assert isinstance(payload["payload"], dict)
    payload["payload"][field] = value
    with pytest.raises(ValidationError):
        ToolEvent.model_validate_json(json.dumps(payload))


def test_snapshot_limit_and_sequence_boundary() -> None:
    payload = event()
    run = ToolEvent.model_validate_json(json.dumps(payload)).payload
    for sequence, runs in [(0, [run]), (1, [run] * 17)]:
        with pytest.raises(ValidationError):
            ToolSnapshotEvent(
                conversationId=uuid4(),
                generationId=uuid4(),
                timestamp=datetime.now(UTC),
                lastSequence=sequence,
                runs=runs,
            )


async def test_disconnect_during_drain_does_not_fail_generation(
    llm_config: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager, live, request, snapshots = worker(llm_config, Segments([("Hallo", None)]))
    peer = next(iter(live.peers))
    manager.subscribe(peer, live.command.requestId, 0, True)

    async def disconnect(value: Peer) -> None:
        manager.detach(value)

    monkeypatch.setattr(manager, "deliver", disconnect)
    await manager._run(live, request, [])
    assert snapshots.events[-1]["type"] == "chat.generation.completed"
    assert not peer.subscriptions and peer.detached


def test_detached_peer_cannot_be_resubscribed(llm_config: Settings) -> None:
    manager, live, _, _ = worker(llm_config, Segments([("Hallo", None)]))
    peer = next(iter(live.peers))
    manager.detach(peer)
    manager.subscribe(peer, live.command.requestId, 0, True)
    peer.offer({"version": 1, "type": "chat.heartbeat"})
    assert not peer.subscriptions and peer.queue.empty() and not live.peers
