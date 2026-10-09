from collections.abc import Callable, Sequence
from math import ceil
from typing import Protocol, cast

from tokenizers import Tokenizer

from noris_ai.core.config import Settings
from noris_ai.llm.provider import ProviderMessage


class EncodedTokens(Protocol):
    @property
    def ids(self) -> list[int]: ...


class LocalTokenizer(Protocol):
    def no_truncation(self) -> None: ...

    def no_padding(self) -> None: ...

    def encode(self, sequence: str, *, add_special_tokens: bool) -> EncodedTokens: ...


class TokenCounter:
    """Offline content tokenization plus conservative chat-template reserves.

    No runtime downloads. A configured unusable file fails startup. Counts remain
    estimates of the provider prompt (its template/system additions are unknown).
    UTF-8 bytes are the fallback upper bound for byte-based GPT-OSS tokenization.
    """

    def __init__(self, config: Settings) -> None:
        self.config = config
        # tokenizers 0.22 has incomplete Python annotations at this library boundary.
        load = cast(Callable[[str], LocalTokenizer], Tokenizer.from_file)  # pyright: ignore[reportUnknownMemberType]
        self.tokenizer = (
            load(str(config.llm_tokenizer_path)) if config.llm_tokenizer_path is not None else None
        )
        if self.tokenizer is not None:
            self.tokenizer.no_truncation()
            self.tokenizer.no_padding()

    def estimate(self, messages: Sequence[ProviderMessage], model_id: str) -> int:
        tokenizer = self.tokenizer if model_id == self.config.llm_tokenizer_model_id else None
        if tokenizer is None:
            content_tokens = sum(len(message.content.encode("utf-8")) for message in messages)
        else:
            content_tokens = sum(
                len(tokenizer.encode(message.content, add_special_tokens=False).ids)
                for message in messages
            )
            content_tokens = ceil(content_tokens * 11 / 10)
        return (
            content_tokens
            + 32 * len(messages)
            + 64
            + self.config.llm_context_safety_tokens
            + self.config.llm_system_reserved_tokens
        )
