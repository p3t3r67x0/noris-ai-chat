"""Internal image inputs, reconstructed from owned storage, never accepted over REST/WS."""

from typing import Self

from pydantic import Field, model_validator

from noris_ai.core.schemas import ApiSchema
from noris_ai.llm.schemas import LLMMessage, LLMModel

IMAGE_MAX_EDGE = 1024
IMAGE_MAX_BYTES = 524_288
# Local conservative reservation, not a claim about a provider's image tokenizer.
IMAGE_TOKEN_RESERVE = 4096


class VisionImage(ApiSchema):
    data_url: str = Field(
        repr=False, max_length=700_000, pattern=r"^data:image/jpeg;base64,[A-Za-z0-9+/]+={0,2}$"
    )


class VisionMessage(LLMMessage):
    images: tuple[VisionImage, ...] = Field(min_length=1, max_length=10, exclude=True, repr=False)

    @model_validator(mode="after")
    def images_are_user_data(self) -> Self:
        if self.role != "user":
            raise ValueError("Images must remain user input")
        return self


def supports_images(model: LLMModel) -> bool:
    # A documented model name or a local vision override cannot authorize images.
    return (
        model.available
        and model.streaming
        and model.vision is True
        and "image" in model.input_modalities
        and "text" in model.input_modalities
    )
