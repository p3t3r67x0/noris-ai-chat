from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from noris_ai.core.schemas import ApiSchema


class LLMMessage(ApiSchema):
    role: Literal["user", "assistant"]
    # Absolute structural bound; configured per-role UTF-16 limits apply at admission.
    content: str = Field(max_length=1_048_576)

    @model_validator(mode="after")
    def user_has_text(self) -> Self:
        # Existing chat paths retain an empty assistant after Stop before the first delta.
        if self.role == "user" and not self.content.strip():
            raise ValueError("User messages must contain text")
        return self

    @field_validator("content")
    @classmethod
    def valid_unicode(cls, value: str) -> str:
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Message must contain valid Unicode") from None
        return value


class LLMModel(ApiSchema):
    id: str = Field(min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._/:-]*$")
    name: str = Field(min_length=1, max_length=120)
    available: bool = True
    streaming: bool = True
    context_window: int = Field(default=8192, ge=256, le=2_000_000)
    # Total generated tokens, including reasoning, rather than visible text only.
    max_output_tokens: int = Field(default=1024, ge=1, le=131_072)
    provider_max_output_tokens: int = Field(default=8192, ge=1, le=131_072)
    provider_limit_evidence: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def output_fits_context(self) -> Self:
        if self.max_output_tokens >= self.context_window:
            raise ValueError("Output token limit must be below the model context window")
        if self.max_output_tokens > self.provider_max_output_tokens:
            raise ValueError("Output exceeds the configured provider capacity")
        if self.provider_max_output_tokens > 8192 and (
            not self.provider_limit_evidence or not self.provider_limit_evidence.strip()
        ):
            raise ValueError("Expanded provider output requires verification evidence")
        return self


class ChatLimits(ApiSchema):
    max_message_chars: int = Field(ge=1, le=1_048_576)
    max_response_chars: int = Field(ge=1, le=1_048_576)
    max_stream_bytes: int = Field(ge=1024, le=67_108_864)
    stream_timeout_ms: int = Field(ge=1000, le=3_615_000)
    stream_idle_timeout_ms: int = Field(ge=1000, le=615_000)


class ModelCatalog(ApiSchema):
    models: list[LLMModel]
    default_model: str | None
    limits: ChatLimits


class ChatRequest(ApiSchema):
    generationId: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    conversationId: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    inputMessageId: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    modelId: str = Field(min_length=1, max_length=200)
    messages: list[LLMMessage] = Field(min_length=1, max_length=100)
    attempt: int = Field(ge=1, le=1000)

    @model_validator(mode="after")
    def validate_path(self) -> Self:
        if self.messages[0].role != "user" or self.messages[-1].role != "user":
            raise ValueError("The active path must begin and end with a user message")
        if any(a.role == b.role for a, b in zip(self.messages, self.messages[1:], strict=False)):
            raise ValueError("Messages must alternate user and assistant roles")
        return self


class ConversationTitleRequest(ApiSchema):
    conversationId: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    inputMessageId: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    modelId: str = Field(min_length=1, max_length=200)
    firstMessage: str = Field(min_length=1, max_length=1024)

    @field_validator("firstMessage")
    @classmethod
    def valid_first_message(cls, value: str) -> str:
        LLMMessage(role="user", content=value)
        return value


class ConversationTitleResponse(ApiSchema):
    conversationId: str
    inputMessageId: str
    title: str = Field(min_length=1, max_length=40)


class StartedEvent(ApiSchema):
    seq: int = Field(ge=1)
    type: Literal["response.started"] = "response.started"


class DeltaEvent(ApiSchema):
    seq: int = Field(ge=1)
    type: Literal["response.output_text.delta"] = "response.output_text.delta"
    delta: str


class CompletedEvent(ApiSchema):
    seq: int = Field(ge=1)
    type: Literal["response.completed"] = "response.completed"


class CancelledEvent(ApiSchema):
    seq: int = Field(ge=1)
    type: Literal["response.cancelled"] = "response.cancelled"


class FailedEvent(ApiSchema):
    seq: int = Field(ge=1)
    type: Literal["response.failed"] = "response.failed"
    code: str
    message: str


StreamEvent = Annotated[
    StartedEvent | DeltaEvent | CompletedEvent | CancelledEvent | FailedEvent,
    Field(discriminator="type"),
]
