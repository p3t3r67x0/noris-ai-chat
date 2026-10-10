"""Synthetic account-free metadata for local simulators; never a live entitlement."""

from noris_ai.llm.provider_models import ProviderModel


def provider_model(model_id: str) -> ProviderModel:
    kind = "embeddings" if "harrier" in model_id else "rerank" if "reranker" in model_id else "text"
    return ProviderModel.model_validate(
        {
            "id": model_id,
            "schema_version": "2.4",
            "is_ready": True,
            "input_modalities": [
                {
                    "type": "text",
                    "supported_inputs": {
                        "max_context_length": {
                            "value": 131072 if "gpt-oss" in model_id else 2000000,
                            "unit": "token",
                        },
                    },
                }
            ],
            "output_modalities": [
                {
                    "type": kind,
                    "streaming": True,
                    "supported_parameters": {
                        "max_tokens": {"max": 131072, "unit": "token"},
                        "max_completion_tokens": {"max": 131072, "unit": "token"},
                    },
                }
            ],
        }
    )


def provider_data(model_id: str) -> dict[str, object]:
    return provider_model(model_id).model_dump(mode="json", exclude_none=True)
