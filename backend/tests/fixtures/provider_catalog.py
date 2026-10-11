"""Synthetic account-free metadata for local simulators; never a live entitlement."""

from noris_ai.llm.provider_models import ProviderModality, ProviderModel


def provider_model(model_id: str, *, vision: bool = False) -> ProviderModel:
    kind = "embeddings" if "harrier" in model_id else "rerank" if "reranker" in model_id else "text"
    model = ProviderModel.model_validate(
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
    if vision:
        model = model.model_copy(
            update={
                "input_modalities": [
                    *(model.input_modalities or []),
                    ProviderModality(type="image"),
                ]
            }
        )
    return model


def provider_data(model_id: str, *, vision: bool = False) -> dict[str, object]:
    return provider_model(model_id, vision=vision).model_dump(mode="json", exclude_none=True)
