from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from noris_ai.learning.policy import LearningInstruction
from noris_ai.llm.continuation import ContinuationInstruction
from noris_ai.llm.provider_models import ProviderModel
from noris_ai.llm.schemas import LLMMessage, LLMModel
from noris_ai.llm.titles import TitleInstruction
from noris_ai.llm.vision import VisionMessage
from noris_ai.research.schemas import ExternalSourceContent, ResearchInstruction

type ProviderMessage = (
    LLMMessage
    | TitleInstruction
    | ContinuationInstruction
    | LearningInstruction
    | ResearchInstruction
    | ExternalSourceContent
)


def provider_payload(message: ProviderMessage) -> dict[str, object]:
    if isinstance(message, VisionMessage):
        parts: list[dict[str, object]] = [{"type": "text", "text": message.content}]
        parts.extend(
            {"type": "image_url", "image_url": {"url": image.data_url}} for image in message.images
        )
        return {"role": "user", "content": parts}
    return message.model_dump()


class LLMProvider(Protocol):
    async def discover_models(self) -> list[ProviderModel]: ...

    def stream(
        self, messages: Sequence[ProviderMessage], model: LLMModel
    ) -> AsyncIterator[str]: ...

    async def aclose(self) -> None: ...
