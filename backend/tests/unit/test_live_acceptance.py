import json
import stat
import sys
from pathlib import Path

import httpx
import pytest

from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.live_acceptance import Observation, ObservedProvider, main, private_json
from noris_ai.llm.openai_compatible import OpenAICompatibleProvider
from noris_ai.llm.schemas import LLMMessage


def test_live_opt_in_is_checked_before_credentials_or_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("NORIS_RUN_LIVE_LLM_SMOKE", raising=False)
    monkeypatch.setattr(sys, "argv", ["live", "server", "--session", str(tmp_path)])
    assert main() == 2
    assert "EXPLICIT_PAID_OPT_IN_REQUIRED" in capsys.readouterr().out
    assert not list(tmp_path.iterdir())


def test_application_access_file_is_private(tmp_path: Path) -> None:
    path = tmp_path / "access.json"
    private_json(path, {"password": "fixture-only"})
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not path.with_suffix(".tmp").exists()


async def test_hard_paid_call_cap_and_observations_never_include_text_or_keys(
    llm_config: Settings, tmp_path: Path
) -> None:
    observation = Observation(tmp_path / "state.json")
    provider = ObservedProvider(llm_config, observation)
    await provider.inner.aclose()
    calls: list[httpx.Request] = []
    payload_text = "fixture-provider-key-never-real"

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        event = {
            "choices": [{"index": 0, "delta": {"content": payload_text}, "finish_reason": "stop"}]
        }
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content="data: " + json.dumps(event) + "\n\ndata: [DONE]\n\n",
        )

    provider.inner = OpenAICompatibleProvider(llm_config, transport=httpx.MockTransport(reply))
    try:
        for _ in range(3):
            _ = [
                text
                async for text in provider.stream(
                    [LLMMessage(role="user", content="test")], llm_config.llm_models[0]
                )
            ]
        with pytest.raises(LLMError) as caught:
            _ = [
                text
                async for text in provider.stream(
                    [LLMMessage(role="user", content="fourth")], llm_config.llm_models[0]
                )
            ]
        assert caught.value.code == "BUDGET_LIMIT"
        assert len(calls) == 3
        state = observation.path.read_text()
        assert payload_text not in state and "test" not in state and "Authorization" not in state
        assert all(call["outcome"] == "completed" for call in observation.calls)
        restored = Observation(observation.path)
        assert restored.calls == observation.calls  # Restart never resets spent calls.
    finally:
        await provider.aclose()
