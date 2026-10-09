/* Generated from backend OpenAPI. Run pnpm api:generate. Do not edit. */
export type Seq = number
export type Type = "response.cancelled"
export type MaxMessageChars = number
export type MaxResponseChars = number
export type MaxStreamBytes = number
export type StreamIdleTimeoutMs = number
export type StreamTimeoutMs = number
export type Attempt = number
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
export type Evidence = ("DOCUMENTED" | "VERIFIED" | "UNKNOWN")
export type Code1 = string
export type Message1 = string
export type Seq3 = number
export type Type3 = "response.failed"
export type Service = "noris-ai"
export type Status = "ok"
export type Version = string
export type Available = boolean
export type ContextWindow = number
export type AsOf = (string | null)
export type CachedInputPointsPerMillion = (number | null)
export type InputPointsPerMillion = (number | null)
export type OutputPointsPerMillion = (number | null)
export type Source = string
export type Description = string
export type DocumentedContextWindow = (number | null)
export type Id = string
export type Lifecycle = ("LTS" | "PRODUCTIVE" | "EXPERIMENTAL" | "DEPRECATED" | "UNKNOWN")
export type MaxOutputTokens = number
export type Name = string
export type Provider = (string | null)
export type ProviderLimitEvidence = (string | null)
export type ProviderMaxOutputTokens = number
export type Reasoning = (boolean | null)
export type ReasoningEffort = (string | null)
export type ReasoningEfforts = string[]
export type ReasoningParameter = (("reasoning_effort" | "chat_template_kwargs") | null)
export type ReleasedAt = (string | null)
export type Sources = string[]
export type Streaming = boolean
export type SupportedOutputTokens = (number | null)
export type ReadSeconds = number
export type TotalSeconds = number
export type TokenLimitParameter = (("max_tokens" | "max_completion_tokens") | null)
export type ToolCalling = (boolean | null)
export type Virtual = boolean
export type Vision = (boolean | null)
export type DefaultModel = (string | null)
export type ErrorCode = (string | null)
export type ExpiresInSeconds = number
export type FetchedAt = (string | null)
export type Models = LLMModel[]
export type RegistryVersion = string
export type Status1 = ("fresh" | "stale")
export type ModelCategory = ("CHAT" | "REASONING" | "VISION" | "EMBEDDING" | "RERANKING" | "UNKNOWN")
export type Status2 = "ready"
export type Seq4 = number
export type Type4 = "response.started"

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
  Evidence: Evidence
  FailedEvent: FailedEvent
  HealthResponse: HealthResponse
  LLMMessage: LLMMessage
  LLMModel: LLMModel
  ModelCatalog: ModelCatalog
  ModelCategory: ModelCategory
  ModelCost: ModelCost
  ReadinessResponse: ReadinessResponse
  StartedEvent: StartedEvent
  TimeoutPolicy: TimeoutPolicy
}
export interface CancelledEvent {
  seq: Seq
  type?: Type
}
export interface ChatLimits {
  max_message_chars: MaxMessageChars
  max_response_chars: MaxResponseChars
  max_stream_bytes: MaxStreamBytes
  stream_idle_timeout_ms: StreamIdleTimeoutMs
  stream_timeout_ms: StreamTimeoutMs
}
export interface ChatRequest {
  attempt: Attempt
  conversationId: Conversationid
  generationId: Generationid
  inputMessageId: Inputmessageid
  messages: Messages
  modelId: Modelid
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
export interface LLMModel {
  available?: Available
  category?: ("CHAT" | "REASONING" | "VISION" | "EMBEDDING" | "RERANKING" | "UNKNOWN")
  context_window?: ContextWindow
  cost?: ModelCost
  description?: Description
  documented_context_window?: DocumentedContextWindow
  evidence?: Evidence1
  id: Id
  lifecycle?: Lifecycle
  max_output_tokens?: MaxOutputTokens
  name: Name
  provider?: Provider
  provider_limit_evidence?: ProviderLimitEvidence
  provider_max_output_tokens?: ProviderMaxOutputTokens
  reasoning?: Reasoning
  reasoning_effort?: ReasoningEffort
  reasoning_efforts?: ReasoningEfforts
  reasoning_parameter?: ReasoningParameter
  released_at?: ReleasedAt
  sources?: Sources
  streaming?: Streaming
  supported_output_tokens?: SupportedOutputTokens
  timeout_policy?: TimeoutPolicy
  token_limit_parameter?: TokenLimitParameter
  tool_calling?: ToolCalling
  virtual?: Virtual
  vision?: Vision
}
export interface ModelCost {
  as_of?: AsOf
  cached_input_points_per_million?: CachedInputPointsPerMillion
  evidence?: ("DOCUMENTED" | "VERIFIED" | "UNKNOWN")
  input_points_per_million?: InputPointsPerMillion
  output_points_per_million?: OutputPointsPerMillion
  source?: Source
}
export interface Evidence1 {
  [k: string]: Evidence
}
export interface TimeoutPolicy {
  read_seconds?: ReadSeconds
  total_seconds?: TotalSeconds
}
export interface ModelCatalog {
  default_model: DefaultModel
  error_code?: ErrorCode
  expires_in_seconds?: ExpiresInSeconds
  fetched_at?: FetchedAt
  limits: ChatLimits
  models: Models
  registry_version?: RegistryVersion
  status?: Status1
}
export interface ReadinessResponse {
  status?: Status2
}
export interface StartedEvent {
  seq: Seq4
  type?: Type4
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
      200: ApiSchemas["StartedEvent"] | ApiSchemas["DeltaEvent"] | ApiSchemas["CompletedEvent"] | ApiSchemas["CancelledEvent"] | ApiSchemas["FailedEvent"]
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
      502: ApiSchemas["ErrorResponse"]
      503: ApiSchemas["ErrorResponse"]
      504: ApiSchemas["ErrorResponse"]
    } }
  }
}
