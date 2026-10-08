from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NORIS_",
        env_file=Path(__file__).resolve().parents[4] / ".env",
        extra="ignore",
        frozen=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://noris_app:noris-app-local-development-only@127.0.0.1:55432/noris_dev"
    )
    migration_database_url: SecretStr | None = None
    readiness_timeout_seconds: float = Field(default=3.0, gt=0, le=30)

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        url = make_url(value.get_secret_value())
        if url.drivername != "postgresql+psycopg" or not url.database:
            raise ValueError("A PostgreSQL URL using the psycopg driver and a database is required")
        return value


class EnvironmentSettings(Settings):
    """Load settings from the environment and explicit values without reading a dotenv file."""

    model_config = SettingsConfigDict(env_file=None)
