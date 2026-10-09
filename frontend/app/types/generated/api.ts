/* Generated from backend OpenAPI. Run pnpm api:generate. Do not edit. */
export type Seq = number
export type Type = "response.cancelled"
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
export type Available = boolean
export type ContextWindow = number
export type Id = string
export type MaxOutputTokens = number
export type Name = string
export type Streaming = boolean
export type DefaultModel = (string | null)
export type Models = LLMModel[]
export type Status1 = "ready"
export type Seq4 = number
export type Type4 = "response.started"

export interface ApiSchemas {
  CancelledEvent: CancelledEvent
  ChatRequest: ChatRequest
  CompletedEvent: CompletedEvent
  DeltaEvent: DeltaEvent
  ErrorDetail: ErrorDetail
  ErrorResponse: ErrorResponse
  FailedEvent: FailedEvent
  HealthResponse: HealthResponse
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
  context_window?: ContextWindow
  id: Id
  max_output_tokens?: MaxOutputTokens
  name: Name
  streaming?: Streaming
}
export interface ModelCatalog {
  default_model: DefaultModel
  models: Models
}
export interface ReadinessResponse {
  status?: Status1
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
      503: ApiSchemas["ErrorResponse"]
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
