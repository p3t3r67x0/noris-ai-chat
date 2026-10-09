import pytest
from pydantic import SecretStr, ValidationError

from noris_ai.core.config import EnvironmentSettings


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NORIS_ENVIRONMENT", "test")
    monkeypatch.setenv("NORIS_READINESS_TIMEOUT_SECONDS", "1.5")
    settings = EnvironmentSettings()
    assert settings.environment == "test"
    assert settings.readiness_timeout_seconds == 1.5


def test_compose_empty_reasoning_setting_keeps_provider_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NORIS_LLM_REASONING_EFFORT", "")
    assert EnvironmentSettings().llm_reasoning_effort is None


@pytest.mark.parametrize("timeout", [0, -1, 31])
def test_readiness_timeout_is_bounded(timeout: float) -> None:
    with pytest.raises(ValidationError):
        EnvironmentSettings(readiness_timeout_seconds=timeout)


def test_database_secret_is_redacted() -> None:
    settings = EnvironmentSettings(
        database_url=SecretStr("postgresql+psycopg://user:test-credential@localhost/noris_test"),
    )
    assert "test-credential" not in repr(settings)
    assert "test-credential" not in settings.model_dump_json()


@pytest.mark.parametrize("url", ["sqlite:///data.db", "postgresql://localhost/db"])
def test_non_postgres_or_unsupported_driver_is_rejected(url: str) -> None:
    with pytest.raises(ValidationError):
        EnvironmentSettings(database_url=SecretStr(url))
