from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from noris_ai.llm.schemas import LLMMessage, LLMModel


class LLMProvider(Protocol):
    def stream(self, messages: Sequence[LLMMessage], model: LLMModel) -> AsyncIterator[str]: ...

    async def aclose(self) -> None: ...
