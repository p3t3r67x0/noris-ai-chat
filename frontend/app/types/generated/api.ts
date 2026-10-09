/* Generated from backend OpenAPI. Run pnpm api:generate. Do not edit. */
export type Seq = number
export type Type = "response.cancelled"
export type MaxContinuations = number
export type MaxMessageChars = number
export type MaxResponseChars = number
export type MaxStreamBytes = number
export type StreamIdleTimeoutMs = number
export type StreamTimeoutMs = number
export type Assistantmessageid = (string | null)
export type Attempt = number
export type Continuationcount = number
export type Conversationid = string
export type Generationid = string
export type Inputmessageid = string
/**
 * @minItems 1
 * @maxItems 100
 */
export type Messages = [LLMMessage, ...(LLMMessage)[]]
export type Content = string
export type Role = ("user" | "assistant")
export type Modelid = string
export type Operation = ("generate" | "continue")
export type Seq1 = number
export type Type1 = "response.completed"
export type Conversationid1 = string
export type Firstmessage = string
export type Inputmessageid1 = string
export type Modelid1 = string
export type Conversationid2 = string
export type Inputmessageid2 = string
export type Title = string
export type Delta = string
export type Seq2 = number
export type Type2 = "response.output_text.delta"
export type Code = string
export type Message = string
export type RequestId = string
export type Code1 = string
export type Message1 = string
export type Seq3 = number
export type Type3 = "response.failed"
export type Service = "noris-ai"
export type Status = "ok"
export type Version = string
export type Reason = "output_limit"
export type Seq4 = number
export type Type4 = "response.incomplete"
export type Available = boolean
export type ContextWindow = number
export type Id = string
export type MaxOutputTokens = number
export type Name = string
export type ProviderContextWindow = number
export type ProviderLimitEvidence = (string | null)
export type ProviderMaxOutputTokens = number
export type ReasoningReserveTokens = number
export type Streaming = boolean
export type DefaultModel = (string | null)
export type Models = LLMModel[]
export type Status1 = "ready"
export type Seq5 = number
export type Type5 = "response.started"

export interface ApiSchemas {
  CancelledEvent: CancelledEvent
  ChatLimits: ChatLimits
  ChatRequest: ChatRequest
  CompletedEvent: CompletedEvent
  ConversationTitleRequest: ConversationTitleRequest
  ConversationTitleResponse: ConversationTitleResponse
  DeltaEvent: DeltaEvent
  ErrorDetail: ErrorDetail
  ErrorResponse: ErrorResponse
  FailedEvent: FailedEvent
  HealthResponse: HealthResponse
  IncompleteEvent: IncompleteEvent
  LLMMessage: LLMMessage
  LLMModel: LLMModel
  ModelCatalog: ModelCatalog
  ReadinessResponse: ReadinessResponse
  StartedEvent: StartedEvent
}
export interface CancelledEvent {
  seq: Seq
  type?: Type
}
export interface ChatLimits {
  max_continuations: MaxContinuations
  max_message_chars: MaxMessageChars
  max_response_chars: MaxResponseChars
  max_stream_bytes: MaxStreamBytes
  stream_idle_timeout_ms: StreamIdleTimeoutMs
  stream_timeout_ms: StreamTimeoutMs
}
export interface ChatRequest {
  assistantMessageId?: Assistantmessageid
  attempt: Attempt
  continuationCount?: Continuationcount
  conversationId: Conversationid
  generationId: Generationid
  inputMessageId: Inputmessageid
  messages: Messages
  modelId: Modelid
  operation?: Operation
}
export interface LLMMessage {
  content: Content
  role: Role
}
export interface CompletedEvent {
  seq: Seq1
  type?: Type1
}
export interface ConversationTitleRequest {
  conversationId: Conversationid1
  firstMessage: Firstmessage
  inputMessageId: Inputmessageid1
  modelId: Modelid1
}
export interface ConversationTitleResponse {
  conversationId: Conversationid2
  inputMessageId: Inputmessageid2
  title: Title
}
export interface DeltaEvent {
  delta: Delta
  seq: Seq2
  type?: Type2
}
export interface ErrorDetail {
  code: Code
  message: Message
  request_id: RequestId
}
export interface ErrorResponse {
  error: ErrorDetail
}
export interface FailedEvent {
  code: Code1
  message: Message1
  seq: Seq3
  type?: Type3
}
export interface HealthResponse {
  service?: Service
  status?: Status
  version: Version
}
export interface IncompleteEvent {
  reason?: Reason
  seq: Seq4
  type?: Type4
}
export interface LLMModel {
  available?: Available
  context_window?: ContextWindow
  id: Id
  max_output_tokens?: MaxOutputTokens
  name: Name
  provider_context_window?: ProviderContextWindow
  provider_limit_evidence?: ProviderLimitEvidence
  provider_max_output_tokens?: ProviderMaxOutputTokens
  reasoning_reserve_tokens?: ReasoningReserveTokens
  streaming?: Streaming
}
export interface ModelCatalog {
  default_model: DefaultModel
  limits: ChatLimits
  models: Models
}
export interface ReadinessResponse {
  status?: Status1
}
export interface StartedEvent {
  seq: Seq5
  type?: Type5
}

export interface ApiPaths {
  "/api/v1/health/live": {
    get: {
      responses: {
      200: ApiSchemas["HealthResponse"]
    } }
  }
  "/api/v1/health/ready": {
    get: {
      responses: {
      200: ApiSchemas["ReadinessResponse"]
      503: ApiSchemas["ErrorResponse"]
    } }
  }
  "/api/v1/llm/chat": {
    post: {
      requestBody: ApiSchemas["ChatRequest"]
      responses: {
      200: ApiSchemas["StartedEvent"] | ApiSchemas["DeltaEvent"] | ApiSchemas["CompletedEvent"] | ApiSchemas["CancelledEvent"] | ApiSchemas["IncompleteEvent"] | ApiSchemas["FailedEvent"]
      400: ApiSchemas["ErrorResponse"]
      401: ApiSchemas["ErrorResponse"]
      403: ApiSchemas["ErrorResponse"]
      408: ApiSchemas["ErrorResponse"]
      409: ApiSchemas["ErrorResponse"]
      413: ApiSchemas["ErrorResponse"]
      415: ApiSchemas["ErrorResponse"]
      422: ApiSchemas["ErrorResponse"]
      429: ApiSchemas["ErrorResponse"]
      500: ApiSchemas["ErrorResponse"]
      503: ApiSchemas["ErrorResponse"]
    } }
  }
  "/api/v1/llm/conversation-title": {
    post: {
      requestBody: ApiSchemas["ConversationTitleRequest"]
      responses: {
      200: ApiSchemas["ConversationTitleResponse"]
      400: ApiSchemas["ErrorResponse"]
      401: ApiSchemas["ErrorResponse"]
      403: ApiSchemas["ErrorResponse"]
      408: ApiSchemas["ErrorResponse"]
      409: ApiSchemas["ErrorResponse"]
      413: ApiSchemas["ErrorResponse"]
      415: ApiSchemas["ErrorResponse"]
      422: ApiSchemas["ErrorResponse"]
      429: ApiSchemas["ErrorResponse"]
      500: ApiSchemas["ErrorResponse"]
      502: ApiSchemas["ErrorResponse"]
      503: ApiSchemas["ErrorResponse"]
      504: ApiSchemas["ErrorResponse"]
    } }
  }
  "/api/v1/llm/models": {
    get: {
      responses: {
      200: ApiSchemas["ModelCatalog"]
      400: ApiSchemas["ErrorResponse"]
      401: ApiSchemas["ErrorResponse"]
      403: ApiSchemas["ErrorResponse"]
      408: ApiSchemas["ErrorResponse"]
      409: ApiSchemas["ErrorResponse"]
      413: ApiSchemas["ErrorResponse"]
      415: ApiSchemas["ErrorResponse"]
      422: ApiSchemas["ErrorResponse"]
      429: ApiSchemas["ErrorResponse"]
      500: ApiSchemas["ErrorResponse"]
      503: ApiSchemas["ErrorResponse"]
    } }
  }
}
