"""Abstract preferences mapped only through exact, evidenced model profiles."""

from typing import TYPE_CHECKING

from noris_ai.llm.errors import LLMError

if TYPE_CHECKING:
    from noris_ai.llm.schemas import LLMModel, ReasoningPreference

# Sofort means lowest supported effort, not zero reasoning or guaranteed latency.
# Pro has no documented profile. A matching provider string alone is insufficient.
PROFILES: dict[str, tuple[str, dict[str, str]]] = {
    "vllm/release/gpt-oss-120b": (
        "reasoning_effort",
        {"instant": "low", "medium": "medium", "high": "high"},
    ),
    "vllm/release/glm-5-2": ("chat_template_kwargs", {"high": "high", "very_high": "max"}),
}


def preference_mapping(model: "LLMModel") -> dict["ReasoningPreference", str]:
    from typing import cast

    profile = PROFILES.get(model.id)
    if (
        profile is None
        or model.virtual
        or model.reasoning is not True
        or not model.sources
        or model.evidence.get("reasoning_parameter", "UNKNOWN") == "UNKNOWN"
        or model.reasoning_parameter != profile[0]
    ):
        return {}
    return {
        cast("ReasoningPreference", preference): effort
        for preference, effort in profile[1].items()
        if effort in model.reasoning_efforts
    }


def apply_preference(model: "LLMModel", preference: "ReasoningPreference | None") -> "LLMModel":
    if preference is None:
        return model
    effort = preference_mapping(model).get(preference)
    if effort is None:
        raise LLMError("REASONING_UNSUPPORTED", 422)
    return model.model_copy(update={"reasoning_effort": effort})
