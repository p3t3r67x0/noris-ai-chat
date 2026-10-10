from decimal import Decimal

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


type Evidence = Literal["DOCUMENTED", "VERIFIED", "UNKNOWN"]
type ModelCategory = Literal["CHAT", "REASONING", "VISION", "EMBEDDING", "RERANKING", "UNKNOWN"]


class TimeoutPolicy(ApiSchema):
    read_seconds: float = Field(default=30, gt=0, le=600)
    total_seconds: float = Field(default=120, gt=0, le=3600)


class ModelCost(ApiSchema):
    evidence: Evidence = "UNKNOWN"
    source: str = "https://ai.noris.de/v1/models"
    currency: Literal["USD"] | None = None
    input_usd_per_million: Decimal | None = Field(default=None, ge=0)
    cached_input_usd_per_million: Decimal | None = Field(default=None, ge=0)
    output_usd_per_million: Decimal | None = Field(default=None, ge=0)
    is_free: bool | None = None
    discount_to_user: Decimal | None = None
    discount_applied: bool = False
    as_of: str | None = None
    input_points_per_million: float | None = Field(default=None, ge=0)
    cached_input_points_per_million: float | None = Field(default=None, ge=0)
    output_points_per_million: float | None = Field(default=None, ge=0)


class LLMModel(ApiSchema):
    id: str = Field(min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._/:-]*$")
    name: str = Field(min_length=1, max_length=120)
    available: bool = True
    streaming: bool = True
    context_window: int = Field(default=8192, ge=256, le=2_000_000)
    # Total generated tokens, including reasoning, rather than visible text only.
    max_output_tokens: int = Field(default=1024, ge=1, le=131_072)
    provider_max_output_tokens: int | None = Field(default=None, ge=1)
    verified_max_output_tokens: int | None = Field(default=None, ge=1, le=131_072)
    effective_context_window: int | None = Field(default=None, ge=256, le=2_000_000)
    effective_max_output_tokens: int | None = Field(default=None, ge=1, le=131_072)
    provider_schema_version: str | None = None
    provider_name: str | None = None
    provider_created_at: str | None = None
    input_modalities: list[str] = Field(default_factory=list)
    output_modalities: list[str] = Field(default_factory=list)
    is_ready: bool | None = None
    chat_approved: bool = False
    provenance: dict[
        str, Literal["PROVIDER", "LOCAL_POLICY", "DOCUMENTATION", "LIVE_TEST", "UNKNOWN"]
    ] = Field(default_factory=dict)
    provider_limit_evidence: str | None = Field(default=None, min_length=1, max_length=500)
    provider: str | None = Field(default=None, max_length=120)
    category: ModelCategory = "UNKNOWN"
    description: str = Field(default="", max_length=500)
    virtual: bool = False
    reasoning: bool | None = None
    vision: bool | None = None
    tool_calling: bool | None = None
    lifecycle: Literal["LTS", "PRODUCTIVE", "EXPERIMENTAL", "DEPRECATED", "UNKNOWN"] = "UNKNOWN"
    released_at: str | None = None
    # Effective policy limits above are distinct from documented provider maxima.
    documented_context_window: int | None = Field(default=None, ge=256, le=2_000_000)
    supported_output_tokens: int | None = Field(default=None, ge=1)
    token_limit_parameter: Literal["max_tokens", "max_completion_tokens"] | None = None
    reasoning_parameter: Literal["reasoning_effort", "chat_template_kwargs"] | None = None
    reasoning_efforts: list[str] = Field(default_factory=list)
    reasoning_effort: str | None = None
    timeout_policy: TimeoutPolicy = Field(default_factory=TimeoutPolicy)
    evidence: dict[str, Evidence] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)
    cost: ModelCost = Field(default_factory=ModelCost)
    estimated_max_cost_usd: Decimal | None = Field(default=None, ge=0)
    provider_context_window: int | None = Field(default=None, ge=256, le=2_000_000)
    reasoning_reserve_tokens: int = Field(default=0, ge=0, le=65_536)

    @model_validator(mode="after")
    def output_fits_context(self) -> Self:
        if (
            self.id == "vllm/release/gpt-oss-120b"
            and max(self.context_window, self.provider_context_window or 0) > 131_072
        ):
            raise ValueError("Context exceeds documented GPT-OSS capacity")
        if self.max_output_tokens + self.reasoning_reserve_tokens >= self.context_window:
            raise ValueError("Output token limit must be below the model context window")
        if (
            self.provider_context_window is not None
            and self.context_window > self.provider_context_window
        ):
            raise ValueError("Context window exceeds confirmed provider capacity")
        if self.max_output_tokens > (self.provider_max_output_tokens or 8192):
            raise ValueError("Output exceeds the configured provider capacity")
        if (
            (self.provider_max_output_tokens or 0) > 8192
            or (self.provider_context_window or 0) > 8192
        ) and (not self.provider_limit_evidence or not self.provider_limit_evidence.strip()):
            raise ValueError("Expanded provider output requires verification evidence")
        if (
            self.verified_max_output_tokens
            and self.max_output_tokens > self.verified_max_output_tokens
        ):
            raise ValueError("Output exceeds live-tested capacity")
        if self.effective_context_window not in (None, self.context_window):
            raise ValueError("Effective context must match the legacy application limit")
        if self.effective_max_output_tokens not in (None, self.max_output_tokens):
            raise ValueError("Effective output must match the legacy application limit")
        if self.documented_context_window and self.context_window > self.documented_context_window:
            raise ValueError("Policy context must not exceed documented context")
        if self.supported_output_tokens and self.max_output_tokens > self.supported_output_tokens:
            raise ValueError("Policy output must not exceed supported output")
        if self.reasoning_effort is not None and (
            not self.reasoning
            or not self.reasoning_parameter
            or self.reasoning_effort not in self.reasoning_efforts
        ):
            raise ValueError("Reasoning effort must be explicitly supported by this model")
        return self


class ChatLimits(ApiSchema):
    max_message_chars: int = Field(ge=1, le=1_048_576)
    max_response_chars: int = Field(ge=1, le=1_048_576)
    max_stream_bytes: int = Field(ge=1024, le=67_108_864)
    stream_timeout_ms: int = Field(ge=1000, le=3_615_000)
    stream_idle_timeout_ms: int = Field(ge=1000, le=615_000)
    max_continuations: int = Field(ge=1, le=20)


class ModelCatalog(ApiSchema):
    models: list[LLMModel]
    default_model: str | None
    limits: ChatLimits
    status: Literal["fresh", "stale"] = "fresh"
    fetched_at: str | None = None
    expires_in_seconds: int = 0
    registry_version: str = "1"
    error_code: str | None = None


class ChatRequest(ApiSchema):
    generationId: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    conversationId: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    inputMessageId: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    modelId: str = Field(min_length=1, max_length=200)
    messages: list[LLMMessage] = Field(min_length=1, max_length=100)
    attempt: int = Field(ge=1, le=1000)
    operation: Literal["generate", "continue"] = "generate"
    assistantMessageId: str | None = Field(
        default=None, min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    continuationCount: int = Field(default=0, ge=0, le=20)

    @model_validator(mode="after")
    def validate_path(self) -> Self:
        last_role = "assistant" if self.operation == "continue" else "user"
        if self.messages[0].role != "user" or self.messages[-1].role != last_role:
            raise ValueError("Invalid active path for this operation")
        if self.operation == "continue":
            if not self.assistantMessageId or not self.messages[-1].content.strip():
                raise ValueError("Continuation requires an existing assistant and its text")
            if self.continuationCount < 1:
                raise ValueError("Continuation count is required")
        elif self.assistantMessageId is not None or self.continuationCount:
            raise ValueError("Generation cannot include continuation metadata")
        if any(a.role == b.role for a, b in zip(self.messages, self.messages[1:], strict=False)):
            raise ValueError("Messages must alternate user and assistant roles")
        return self


class PersistedChatRequest(ChatRequest):
    """Trusted database context; REST clients retain their 100-message cap."""

    messages: list[LLMMessage] = Field(min_length=1, max_length=10_001)


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


class IncompleteEvent(ApiSchema):
    seq: int = Field(ge=1)
    type: Literal["response.incomplete"] = "response.incomplete"
    reason: Literal["output_limit"] = "output_limit"


class FailedEvent(ApiSchema):
    seq: int = Field(ge=1)
    type: Literal["response.failed"] = "response.failed"
    code: str
    message: str


StreamEvent = Annotated[
    StartedEvent | DeltaEvent | CompletedEvent | CancelledEvent | IncompleteEvent | FailedEvent,
    Field(discriminator="type"),
]
