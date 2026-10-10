from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from noris_ai.llm.continuation import ContinuationInstruction
from noris_ai.llm.provider_models import ProviderModel
from noris_ai.llm.schemas import LLMMessage, LLMModel
from noris_ai.llm.titles import TitleInstruction

type ProviderMessage = LLMMessage | TitleInstruction | ContinuationInstruction


class LLMProvider(Protocol):
    async def discover_models(self) -> list[ProviderModel]: ...

    def stream(
        self, messages: Sequence[ProviderMessage], model: LLMModel
    ) -> AsyncIterator[str]: ...

    async def aclose(self) -> None: ...
