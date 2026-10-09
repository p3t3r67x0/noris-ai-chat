import os

import pytest
from pydantic import SecretStr

from noris_ai.core.config import EnvironmentSettings, Settings
from noris_ai.llm.schemas import LLMMessage, LLMModel

# Test discovery must not instantiate a live provider or inherit local model limits.
# Explicit Settings passed by provider tests still override these environment defaults.
os.environ["NORIS_LLM_PROVIDER"] = "disabled"
os.environ["NORIS_LLM_MODELS"] = "[]"


@pytest.fixture
def llm_config() -> Settings:
    return EnvironmentSettings(
        environment="test",
        llm_provider="openai-compatible",
        llm_base_url="http://127.0.0.1:9999/v1",
        llm_allowed_hosts=("127.0.0.1",),
        llm_api_key=SecretStr("fixture-provider-key-never-real"),
        llm_access_username="fixture-user",
        llm_access_password=SecretStr("fixture-application-password-never-real"),
        llm_allowed_origins=("http://localhost:3000",),
        llm_models=(
            LLMModel(
                id="fixture-alpha",
                name="Fixture Alpha",
                category="CHAT",
                token_limit_parameter="max_tokens",  # noqa: S106 - parameter name, no secret
                reasoning=True,
                reasoning_parameter="reasoning_effort",
                reasoning_efforts=["low", "medium", "high"],
                sources=["fixture:local"],
                evidence={
                    "category": "VERIFIED",
                    "streaming": "VERIFIED",
                    "token_limit_parameter": "VERIFIED",
                    "reasoning_parameter": "VERIFIED",
                },
            ),
            LLMModel(
                id="fixture-beta",
                name="Fixture Beta",
                category="CHAT",
                token_limit_parameter="max_tokens",  # noqa: S106 - parameter name, no secret
                sources=["fixture:local"],
                evidence={
                    "category": "VERIFIED",
                    "streaming": "VERIFIED",
                    "token_limit_parameter": "VERIFIED",
                },
            ),
            LLMModel(id="fixture-offline", name="Fixture Offline", available=False),
        ),
        llm_default_model="fixture-alpha",
    )


@pytest.fixture
def llm_messages() -> list[LLMMessage]:
    return [LLMMessage(role="user", content="Hallo 🌍")]
