"""Exact-ID local chat contracts and safety policies, separate from provider facts.

Legacy LLMModel overrides remain accepted as operator policy, never provider evidence.
"""

from typing import TYPE_CHECKING

from pydantic import ValidationError

if TYPE_CHECKING:
    from noris_ai.core.config import Settings
    from noris_ai.llm.provider_models import ProviderModel

from noris_ai.llm.schemas import LLMModel, ModelCategory, TimeoutPolicy

REGISTRY_VERSION = "2026-10-10.1"
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
                "documented_context_window": "UNKNOWN",
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
    8192,
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
    16384,
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
_glm_flash = chat_model(
    "vllm/qsu/glm-5-3-flash",
    "GLM 5.3 Flash",
    "Z.AI (Zhipu)",
    "CHAT",
    "Schnelles Chatmodell · Experimental",
    16384,
    8192,
    API_SOURCE,
    reasoning=False,
    vision=False,
    lifecycle="EXPERIMENTAL",
)
_glm_flash = _glm_flash.model_copy(update={"reasoning": None})

REGISTRY: dict[str, LLMModel] = {
    model.id: model
    for model in [
        _gpt,
        _glm,
        _glm_flash,
        chat_model(
            "vllm/qsu/deepseek-v41-flash",
            "DeepSeek V4.1 Flash",
            "DeepSeek",
            "CHAT",
            "Schnelles Chatmodell · Experimental",
            8192,
            4096,
            API_SOURCE,
            reasoning=False,
            vision=False,
            lifecycle="EXPERIMENTAL",
        ).model_copy(update={"reasoning": None}),
        chat_model(
            "vllm/qsu/qwen3.8-27b",
            "Qwen3.8 27B",
            "Qwen (Alibaba)",
            "CHAT",
            "Für allgemeine Fragen und Coding · Experimental",
            8192,
            4096,
            API_SOURCE,
            reasoning=False,
            vision=False,
            lifecycle="EXPERIMENTAL",
        ).model_copy(update={"reasoning": None}),
        chat_model(
            "vllm/release/gemma-4-31b-it",
            "Gemma 4 31B",
            "Google",
            "VISION",
            "Für allgemeine Fragen",
            8192,
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
            "Qwen3.6 27B",
            "Qwen (Alibaba)",
            "VISION",
            "Für allgemeine Fragen und Coding · Experimental",
            8192,
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


def resolve_model(facts: "ProviderModel", config: "Settings") -> LLMModel:
    """Apply operator policy without allowing it to manufacture provider facts."""
    from datetime import UTC, datetime

    from noris_ai.llm.schemas import ModelCost

    policy = classify(facts.id, config.llm_models)
    inputs = facts.input_modalities or []
    outputs = facts.output_modalities or []
    text_inputs = [item for item in inputs if item.type == "text"]
    text_outputs = [item for item in outputs if item.type == "text"]
    output_types = {item.type for item in outputs}
    category: ModelCategory = "UNKNOWN"
    streaming = bool(text_outputs) and all(item.streaming is True for item in text_outputs)
    if "embeddings" in output_types:
        category = "EMBEDDING"
    elif "rerank" in output_types:
        category = "RERANKING"
    elif text_inputs and text_outputs and streaming:
        category = "CHAT"
    vision = any(item.type == "image" for item in inputs) if inputs else None
    reasoning = (
        True
        if any(
            name in item.supported_parameters
            for item in text_outputs
            for name in ("reasoning_effort", "chat_template_kwargs")
        )
        else (policy.reasoning if policy.evidence.get("reasoning") == "DOCUMENTED" else None)
    )
    if category == "CHAT":
        if vision:
            category = "VISION"
        elif reasoning:
            category = "REASONING"
    approved = chat_compatible(policy)
    context_values = [
        item.supported_inputs.max_context_length.value
        for item in text_inputs
        if item.supported_inputs
        and item.supported_inputs.max_context_length
        and item.supported_inputs.max_context_length.unit == "token"
        and item.supported_inputs.max_context_length.value is not None
    ]
    context = min(context_values) if context_values else None
    token_parameter = policy.token_limit_parameter
    output_values: list[int] = []
    for item in text_outputs:
        parameter = item.token_parameter(token_parameter or "max_tokens")
        if parameter and parameter.unit == "token" and parameter.max is not None:
            output_values.append(parameter.max)
        if item.max_length and item.max_length.unit == "token" and item.max_length.value:
            output_values.append(item.max_length.value)
    output = min(output_values) if output_values else None
    # Legacy capacity declarations are operator caps, never dynamic provider facts.
    override = next((item for item in config.llm_models if item.id == facts.id), None)
    operator_context = override.provider_context_window if override else None
    operator_output = override.provider_max_output_tokens if override else None
    effective_context = min(policy.context_window, context or 8192, operator_context or 2_000_000)
    verified = policy.verified_max_output_tokens
    effective_output = min(
        policy.max_output_tokens,
        config.llm_max_output_tokens,
        output or 1024,
        operator_output or 131_072,
        verified or 131_072,
        effective_context
        - policy.reasoning_reserve_tokens
        - config.llm_context_safety_tokens
        - config.llm_system_reserved_tokens
        - 97,
    )
    available = (
        approved
        and facts.compatible_version
        and facts.is_ready is True
        and category in ("CHAT", "REASONING", "VISION")
        and streaming
        and effective_context >= 256
        and effective_output >= 1
    )
    values = policy.model_dump() | {
        "name": policy.name if approved else (facts.name or "Unbekanntes Modell"),
        "provider_name": facts.name,
        "category": category,
        "available": available,
        "chat_approved": approved,
        "streaming": streaming,
        "vision": vision,
        "reasoning": reasoning,
        "context_window": max(256, effective_context),
        "max_output_tokens": max(1, effective_output),
        "effective_context_window": max(256, effective_context),
        "effective_max_output_tokens": max(1, effective_output),
        "provider_context_window": context if context and context >= 256 else None,
        "provider_max_output_tokens": output,
        "documented_context_window": context if context and context >= 256 else None,
        "supported_output_tokens": output,
        "provider_limit_evidence": "Provider-reported GET /models; not a live generation test",
        "provider_schema_version": facts.schema_version,
        "provider_created_at": datetime.fromtimestamp(facts.created, UTC).isoformat()
        if facts.created is not None and facts.created <= 253402300799
        else None,
        "input_modalities": [item.type for item in inputs],
        "output_modalities": [item.type for item in outputs],
        "is_ready": facts.is_ready,
        "cost": ModelCost(),
        "evidence": policy.evidence
        | {
            "category": "DOCUMENTED" if category != "UNKNOWN" else "UNKNOWN",
            "streaming": "DOCUMENTED" if text_outputs else "UNKNOWN",
            "vision": "DOCUMENTED" if inputs else "UNKNOWN",
            "documented_context_window": "DOCUMENTED" if context else "UNKNOWN",
            "supported_output_tokens": "DOCUMENTED" if output else "UNKNOWN",
        },
        "provenance": {
            "category": "PROVIDER" if category != "UNKNOWN" else "UNKNOWN",
            "streaming": "PROVIDER" if text_outputs else "UNKNOWN",
            "vision": "PROVIDER" if inputs else "UNKNOWN",
            "reasoning": "DOCUMENTATION" if reasoning is not None else "UNKNOWN",
            "provider_context_window": "PROVIDER" if context else "UNKNOWN",
            "provider_max_output_tokens": "PROVIDER" if output else "UNKNOWN",
            "verified_max_output_tokens": "LIVE_TEST" if verified else "UNKNOWN",
            "effective_context_window": "LOCAL_POLICY",
            "effective_max_output_tokens": "LOCAL_POLICY",
            "chat_approved": "LOCAL_POLICY",
            "name": "LOCAL_POLICY" if approved else "PROVIDER",
            "is_ready": "PROVIDER" if facts.is_ready is not None else "UNKNOWN",
        },
    }
    try:
        return LLMModel.model_validate(values)
    except ValidationError:
        # Conflicting provider contracts are visible only to discovery, never admitted.
        return LLMModel(
            id=facts.id, name=facts.name or "Unbekanntes Modell", available=False, streaming=False
        )
