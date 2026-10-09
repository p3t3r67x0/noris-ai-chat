import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic

from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.provider import LLMProvider
from noris_ai.llm.registry import REGISTRY_VERSION, chat_compatible, classify
from noris_ai.llm.schemas import LLMModel, ModelCatalog


class ModelCatalogService:
    """One authority for discovery, selection and admission, per backend worker.

    Stale catalogs may be displayed under explicit policy but never authorize a request.
    Success (including an empty list) replaces all previous entitlements atomically.
    """

    def __init__(
        self, config: Settings, provider: LLMProvider | None, clock: Callable[[], float] = monotonic
    ) -> None:
        self.config, self.provider, self.clock = config, provider, clock
        self._lock = asyncio.Lock()
        self._last: ModelCatalog | None = None
        self._expires = 0.0
        self._retry_at = 0.0
        self._error: LLMError | None = None

    def invalidate(self) -> None:
        self._last = None
        self._expires = self._retry_at = 0
        self._error = None

    async def get(self, *, allow_stale: bool = True) -> ModelCatalog:
        async with self._lock:
            now = self.clock()
            if self._last is not None and now < self._expires:
                return self._last.model_copy(
                    update={
                        "expires_in_seconds": max(1, int(self._expires - now)),
                    }
                )
            if now >= self._retry_at:
                try:
                    if self.provider is None:
                        raise LLMError("LLM_DISABLED", 503)
                    async with asyncio.timeout(self.config.llm_discovery_timeout_seconds):
                        ids = await self.provider.discover_models()
                    models = [classify(model_id, self.config.llm_models) for model_id in ids]
                    models = [model for model in models if chat_compatible(model)]
                    models.sort(key=lambda model: (not model.virtual, model.name.casefold()))
                    # The legacy reasoning option applies ONLY to exact GPT-OSS metadata.
                    configured_effort = self.config.llm_reasoning_effort
                    if configured_effort:
                        models = [
                            model.model_copy(update={"reasoning_effort": configured_effort})
                            if model.id == "vllm/release/gpt-oss-120b"
                            and model.reasoning_effort is None
                            and configured_effort in model.reasoning_efforts
                            else model
                            for model in models
                        ]
                    default = self.config.llm_default_model
                    if not any(model.id == default for model in models):
                        default = models[0].id if models else None
                    self._last = ModelCatalog(
                        models=models,
                        default_model=default,
                        fetched_at=datetime.now(UTC).isoformat(),
                        registry_version=REGISTRY_VERSION,
                    )
                    self._expires = self.clock() + self.config.llm_catalog_ttl_seconds
                    self._error = None
                    return self._last.model_copy(
                        update={
                            "expires_in_seconds": int(self.config.llm_catalog_ttl_seconds),
                        }
                    )
                except TimeoutError:
                    self._error = LLMError("TIMEOUT", 504)
                except LLMError as error:
                    self._error = error
                self._retry_at = self.clock() + self.config.llm_discovery_retry_after_seconds
                if self._error and self._error.code in (
                    "PROVIDER_AUTH_FAILED",
                    "MODEL_UNAVAILABLE",
                ):
                    self._last = None  # Revoked access never uses stale display policy.
            if (
                allow_stale
                and self._last is not None
                and self.config.llm_catalog_stale_seconds > 0
                and self.clock() < self._expires + self.config.llm_catalog_stale_seconds
            ):
                return self._last.model_copy(
                    update={
                        "status": "stale",
                        "default_model": None,
                        "models": [
                            model.model_copy(update={"available": False})
                            for model in self._last.models
                        ],
                        "error_code": self._error.code if self._error else "PROVIDER_ERROR",
                    }
                )
            raise self._error or LLMError("PROVIDER_ERROR")

    async def require(self, model_id: str) -> LLMModel:
        catalog = await self.get(allow_stale=False)
        model = next((model for model in catalog.models if model.id == model_id), None)
        if model is None:
            raise LLMError("MODEL_UNAVAILABLE", 400)
        return model
