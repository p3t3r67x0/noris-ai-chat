"""Versioned, exact-ID metadata. Discovery confirms access, never capabilities.

Sources reviewed 2026-10-09. Output sizes are local policy, not provider maxima.
No prefix matching, display-name normalization or inferred model capabilities.
"""

from pydantic import ValidationError

from noris_ai.llm.schemas import LLMModel, ModelCategory, TimeoutPolicy

REGISTRY_VERSION = "2026-10-09.2"
API_SOURCE = "https://noris.cloud/nai/api/chat-completions/"


def chat_model(
    model_id: str,
    name: str,
    provider: str,
    category: ModelCategory,
    description: str,
    context: int,
    output: int,
    source: str,
    *,
    reasoning: bool,
    vision: bool,
    lifecycle: str,
    tool_calling: bool | None = None,
    released_at: str | None = None,
) -> LLMModel:
    return LLMModel.model_validate(
        {
            "id": model_id,
            "name": name,
            "provider": provider,
            "category": category,
            "description": description,
            "context_window": context,
            "max_output_tokens": output,
            "documented_context_window": context,
            "reasoning": reasoning,
            "vision": vision,
            "tool_calling": tool_calling,
            "lifecycle": lifecycle,
            "released_at": released_at,
            "token_limit_parameter": "max_tokens",
            "sources": [source, API_SOURCE],
            "timeout_policy": TimeoutPolicy(read_seconds=60, total_seconds=120)
            if reasoning
            else TimeoutPolicy(),
            "evidence": {
                "category": "DOCUMENTED",
                "streaming": "DOCUMENTED",
                "reasoning": "DOCUMENTED",
                "vision": "DOCUMENTED",
                "tool_calling": "DOCUMENTED" if tool_calling is not None else "UNKNOWN",
                "documented_context_window": "DOCUMENTED",
                "supported_output_tokens": "UNKNOWN",
                "token_limit_parameter": "DOCUMENTED",
                "lifecycle": "DOCUMENTED",
                "released_at": "DOCUMENTED" if released_at else "UNKNOWN",
            },
        }
    )


_gpt = chat_model(
    "vllm/release/gpt-oss-120b",
    "GPT-OSS 120B",
    "OpenAI",
    "REASONING",
    "Für komplexe Fragen und Entwicklung",
    131072,
    4096,
    "https://noris.cloud/nai/models/gpt-oss-120b/",
    reasoning=True,
    vision=False,
    lifecycle="LTS",
    tool_calling=True,
    released_at="2025-08",
)
_gpt = _gpt.model_copy(
    update={
        "reasoning_parameter": "reasoning_effort",
        "reasoning_efforts": ["low", "medium", "high"],
        "sources": [
            *_gpt.sources,
            "https://noris.cloud/nai/concepts/reasoning/",
            "repo:docs/ETAPPE-2.1-LIVE-ABNAHME.md",
        ],
        "evidence": {**_gpt.evidence, "reasoning_parameter": "VERIFIED"},
    }
)
_glm = chat_model(
    "vllm/release/glm-5-2",
    "GLM 5.2",
    "Z.AI (Zhipu)",
    "REASONING",
    "Für tiefgehendes Reasoning und Coding · Experimental",
    1000000,
    8192,
    "https://noris.cloud/nai/models/glm-5-2/",
    reasoning=True,
    vision=False,
    lifecycle="EXPERIMENTAL",
)
_glm = _glm.model_copy(
    update={
        "reasoning_parameter": "chat_template_kwargs",
        "reasoning_efforts": ["high", "max"],
        "evidence": {**_glm.evidence, "reasoning_parameter": "DOCUMENTED"},
    }
)
# GLM 5.3 Flash: live catalog verification via GET /v1/models on 2026-10-09
# (is_ready, 1,048,576-token context, max_tokens output parameter, streaming).
# No reasoning parameter is documented for this model; none is configured.
_glm_flash = chat_model(
    "vllm/qsu/glm-5-3-flash",
    "GLM 5.3 Flash",
    "Z.AI (Zhipu)",
    "CHAT",
    "Schnelles Chatmodell mit großem Kontext · Experimental",
    1048576,
    8192,
    API_SOURCE,
    reasoning=False,
    vision=False,
    lifecycle="EXPERIMENTAL",
)
_glm_flash = _glm_flash.model_copy(
    update={
        "reasoning": None,
        "supported_output_tokens": 1_048_576,
        "provider_context_window": 1_048_576,
        "provider_limit_evidence": (
            "Noris GET /v1/models, 2026-10-09: context_length 1048576; "
            "max_tokens max 1048576; streaming true"
        ),
        "sources": [
            API_SOURCE,
            "live:GET /v1/models 2026-10-09",
        ],
        "evidence": {
            **_glm_flash.evidence,
            "reasoning": "UNKNOWN",
            "supported_output_tokens": "DOCUMENTED",
            "released_at": "UNKNOWN",
        },
    }
)

REGISTRY: dict[str, LLMModel] = {
    model.id: model
    for model in [
        _gpt,
        _glm,
        _glm_flash,
        chat_model(
            "vllm/release/gemma-4-31b-it",
            "Gemma 4 31B",
            "Google",
            "VISION",
            "Für allgemeine Fragen",
            262144,
            2048,
            "https://noris.cloud/nai/models/gemma-4-31b-it/",
            reasoning=True,
            vision=True,
            lifecycle="PRODUCTIVE",
            tool_calling=True,
            released_at="2026-06",
        ),
        chat_model(
            "vllm/release/qwen3.6-27b",
            "Qwen 3.6 27B",
            "Qwen (Alibaba)",
            "VISION",
            "Für allgemeine Fragen und Coding · Experimental",
            262144,
            4096,
            "https://noris.cloud/nai/models/qwen36-27b/",
            reasoning=True,
            vision=True,
            lifecycle="EXPERIMENTAL",
        ),
        LLMModel(
            id="smart_router",
            name="Automatisch",
            provider="Noris",
            category="CHAT",
            description="Noris wählt das passende Modell",
            virtual=True,
            context_window=8192,
            max_output_tokens=2048,
            token_limit_parameter="max_tokens",  # noqa: S106 - parameter name, no secret
            sources=["https://noris.cloud/nai/concepts/smart-router/", API_SOURCE],
            evidence={
                "category": "DOCUMENTED",
                "streaming": "DOCUMENTED",
                "token_limit_parameter": "DOCUMENTED",
                "documented_context_window": "UNKNOWN",
                "supported_output_tokens": "UNKNOWN",
            },
        ),
        LLMModel(
            id="vllm/release/harrier-oss-v1-0.6b",
            name="Harrier OSS v1 0.6B",
            category="EMBEDDING",
            streaming=False,
            sources=["https://noris.cloud/nai/models/harrier-oss-v1-06b/"],
            evidence={"category": "DOCUMENTED"},
        ),
        LLMModel(
            id="vllm/release/jina-reranker-v2-base-multilingual",
            name="Jina Reranker v2 Multilingual",
            category="RERANKING",
            streaming=False,
            sources=["https://noris.cloud/nai/models/jina-reranker-v2/"],
            evidence={"category": "DOCUMENTED"},
        ),
        LLMModel(
            id="vllm/release/bge-reranker-v2-m3",
            name="BGE Reranker v2 M3",
            category="RERANKING",
            streaming=False,
            sources=["https://noris.cloud/nai/models/bge-reranker-v2-m3/"],
            evidence={"category": "DOCUMENTED"},
        ),
    ]
}


def classify(model_id: str, overrides: tuple[LLMModel, ...]) -> LLMModel:
    known = REGISTRY.get(model_id)
    override = next((model for model in overrides if model.id == model_id), None)
    if known is None:
        return (
            override
            if override is not None
            else LLMModel(
                id=model_id,
                name="Unbekanntes Modell",
                streaming=False,
                available=False,
            )
        )
    if override is None:
        return known
    # Preserve documented classification of non-chat models even with operator overrides.
    if known.category in ("EMBEDDING", "RERANKING"):
        return known
    values = known.model_dump() | override.model_dump(exclude_unset=True)
    try:
        return LLMModel.model_validate(values)
    except ValidationError:
        return known.model_copy(update={"available": False})


def chat_compatible(model: LLMModel) -> bool:
    return (
        model.category in ("CHAT", "REASONING", "VISION")
        and model.available
        and model.streaming
        and model.lifecycle != "DEPRECATED"
        and model.token_limit_parameter is not None
        and bool(model.sources)
        and all(
            model.evidence.get(field, "UNKNOWN") != "UNKNOWN"
            for field in ("category", "streaming", "token_limit_parameter")
        )
    )
