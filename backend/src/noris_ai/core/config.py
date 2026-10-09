from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from noris_ai.llm.schemas import LLMModel


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NORIS_",
        env_file=Path(__file__).resolve().parents[4] / ".env",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://noris_app:noris-app-local-development-only@127.0.0.1:55432/noris_dev"
    )
    migration_database_url: SecretStr | None = None
    readiness_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    llm_provider: Literal["disabled", "openai-compatible"] = "disabled"
    llm_base_url: str | None = None
    llm_allowed_hosts: tuple[str, ...] = ()
    llm_api_key: SecretStr | None = None
    llm_access_username: str = ""
    llm_access_password: SecretStr | None = None
    llm_allowed_origins: tuple[str, ...] = ()
    llm_models: tuple[LLMModel, ...] = ()
    llm_default_model: str | None = None
    llm_token_limit_parameter: Literal["max_tokens", "max_completion_tokens"] = Field(
        default="max_tokens"
    )
    llm_reasoning_effort: Literal["low", "medium", "high"] | None = None
    llm_connect_timeout_seconds: float = Field(default=5, gt=0, le=30)
    llm_read_timeout_seconds: float = Field(default=120, ge=1, le=600)
    llm_total_timeout_seconds: float = Field(default=1800, ge=1, le=3600)
    llm_heartbeat_seconds: float = Field(default=10, ge=1, le=30)
    llm_title_timeout_seconds: float = Field(default=6, gt=0, le=30)
    llm_title_max_output_tokens: int = Field(default=96, ge=1, le=256)
    llm_max_concurrent: int = Field(default=4, ge=1, le=32)
    llm_requests_per_minute: int = Field(default=20, ge=1, le=120)
    llm_daily_token_budget: int = Field(default=100_000, ge=1, le=10_000_000)
    llm_max_request_bytes: int = Field(default=1_048_576, ge=1024, le=8_388_608)
    llm_max_upstream_bytes: int = Field(default=16_777_216, ge=1024, le=67_108_864)
    llm_max_stream_bytes: int = Field(default=16_777_216, ge=1024, le=67_108_864)
    llm_max_message_chars: int = Field(default=32_000, ge=1, le=1_048_576)
    llm_max_response_chars: int = Field(default=262_144, ge=1, le=1_048_576)
    llm_max_output_tokens: int = Field(default=8192, ge=1, le=131_072)
    llm_context_safety_tokens: int = Field(default=512, ge=64, le=16_384)

    @model_validator(mode="after")
    def validate_llm_configuration(self) -> Self:
        if max(self.llm_connect_timeout_seconds, self.llm_read_timeout_seconds) > (
            self.llm_total_timeout_seconds
        ):
            raise ValueError("Connection and idle timeouts must fit within total time")
        if any(model.max_output_tokens > self.llm_max_output_tokens for model in self.llm_models):
            raise ValueError("Model output exceeds the application token ceiling")
        if any(
            model.max_output_tokens + self.llm_context_safety_tokens + 96 >= model.context_window
            for model in self.llm_models
        ):
            raise ValueError("Context must leave room for prompt and safety reserve")
        if self.llm_provider == "disabled":
            return self
        key, password = self.llm_api_key, self.llm_access_password
        if not self.llm_base_url or key is None or not key.get_secret_value().strip():
            raise ValueError("Enabled LLM provider requires an explicit base URL and API key")
        if not key.get_secret_value().isascii() or any(
            ord(character) < 32 or ord(character) == 127 for character in key.get_secret_value()
        ):
            raise ValueError("Provider key must be a valid ASCII header value")
        if (
            not self.llm_access_username
            or password is None
            or len(password.get_secret_value()) < 32
        ):
            raise ValueError(
                "Enabled LLM provider requires an access user and a 32-character password"
            )
        if ":" in self.llm_access_username or any(
            not value.isascii()
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
            for value in (self.llm_access_username, password.get_secret_value())
        ):
            raise ValueError("Application access credentials must use printable ASCII")
        if key.get_secret_value() == password.get_secret_value():
            raise ValueError("Provider key and application access password must be different")
        url = urlsplit(self.llm_base_url)
        local_http = self.environment != "production" and url.hostname in (
            "127.0.0.1",
            "localhost",
            "::1",
        )
        if url.scheme != "https" and not (url.scheme == "http" and local_http):
            raise ValueError("Provider requires HTTPS (loopback HTTP is allowed for local tests)")
        if (
            not url.hostname
            or url.hostname not in self.llm_allowed_hosts
            or url.username
            or url.password
            or url.query
            or url.fragment
            or any(c in self.llm_base_url for c in ("\r", "\n", "\\"))
        ):
            raise ValueError(
                "Provider URL must use an explicitly allowed host without credentials or query"
            )
        if not self.llm_allowed_origins:
            raise ValueError("Enabled LLM provider requires explicit browser origins")
        for origin in self.llm_allowed_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in ("http", "https")
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
            ):
                raise ValueError("Browser origins must be exact scheme/host/port values")
            if self.environment == "production" and parsed.scheme != "https":
                raise ValueError("Production browser origins require HTTPS")
        ids = [model.id for model in self.llm_models]
        usable = [model.id for model in self.llm_models if model.available and model.streaming]
        if not usable or len(set(ids)) != len(ids):
            raise ValueError(
                "Configure unique model IDs and at least one available streaming model"
            )
        if self.llm_default_model not in usable:
            raise ValueError("Default model must be a configured available streaming model")
        return self

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        url = make_url(value.get_secret_value())
        if url.drivername != "postgresql+psycopg" or not url.database:
            raise ValueError("A PostgreSQL URL using the psycopg driver and a database is required")
        return value

    @field_validator("llm_reasoning_effort", mode="before")
    @classmethod
    def empty_reasoning_setting(cls, value: object) -> object:
        return None if value == "" else value


class EnvironmentSettings(Settings):
    """Load settings from the environment and explicit values without reading a dotenv file."""

    model_config = SettingsConfigDict(env_file=None)
