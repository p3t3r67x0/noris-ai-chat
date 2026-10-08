import pytest
from pydantic import SecretStr, ValidationError

from noris_ai.core.config import Settings


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NORIS_ENVIRONMENT", "test")
    monkeypatch.setenv("NORIS_READINESS_TIMEOUT_SECONDS", "1.5")
    settings = Settings(_env_file=None)
    assert settings.environment == "test"
    assert settings.readiness_timeout_seconds == 1.5


@pytest.mark.parametrize("timeout", [0, -1, 31])
def test_readiness_timeout_is_bounded(timeout: float) -> None:
    with pytest.raises(ValidationError):
        Settings(readiness_timeout_seconds=timeout, _env_file=None)


def test_database_secret_is_redacted() -> None:
    settings = Settings(
        database_url=SecretStr("postgresql+psycopg://user:test-credential@localhost/noris_test"),
        _env_file=None,
    )
    assert "test-credential" not in repr(settings)
    assert "test-credential" not in settings.model_dump_json()


@pytest.mark.parametrize("url", ["sqlite:///data.db", "postgresql://localhost/db"])
def test_non_postgres_or_unsupported_driver_is_rejected(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=SecretStr(url), _env_file=None)
