/* Generated from backend OpenAPI. Run pnpm api:generate. Do not edit. */
export type Boundaryparentid = (string | null)
export type Activeleafmessageid = (string | null)
export type Archivedat = (string | null)
export type Createdat = string
export type Id = string
export type Lastmessageat = (string | null)
export type Title = string
export type Titlesource = ("fallback" | "generated" | "manual")
export type Updatedat = string
export type Version = number
export type Hasmore = boolean
export type Leafmessageid = (string | null)
export type Content = string
export type Continuationcount = number
export type Conversationid = string
export type Createdat1 = string
export type Editedfrommessageid = (string | null)
export type Errorcode = (string | null)
export type Errormessage = (string | null)
export type Generationid = (string | null)
export type Id1 = string
export type Modelid = (string | null)
export type Parentmessageid = (string | null)
export type Role = ("user" | "assistant")
export type Status = ("pending" | "streaming" | "completed" | "incomplete" | "cancelled" | "failed")
export type Updatedat1 = string
export type Messages = MessageResponse[]
export type Nextcursor = (string | null)
export type Index = number
export type Messageid = string
export type Nextmessageid = (string | null)
export type Previousmessageid = (string | null)
export type Total = number
export type Variants = VariantSummary[]
export type Seq = number
export type Type = "response.cancelled"
export type Activeconversationid = (string | null)
export type Activeleafmessageid1 = (string | null)
export type Archivedat1 = (string | null)
export type Createdat2 = string
export type Id2 = string
export type Title1 = string
export type Titlesource1 = ("fallback" | "generated" | "manual")
export type Updatedat2 = string
export type Version1 = number
/**
 * @maxItems 500
 */
export type Conversations = ImportConversation[]
export type Content1 = string
export type Continuationcount1 = number
export type Conversationid1 = string
export type Createdat3 = string
export type Editedfrommessageid1 = (string | null)
export type Errorcode1 = (string | null)
export type Errormessage1 = (string | null)
export type Id3 = string
export type Modelid1 = (string | null)
export type Parentmessageid1 = (string | null)
export type Role1 = ("user" | "assistant")
export type Status1 = ("pending" | "streaming" | "completed" | "incomplete" | "cancelled" | "failed")
export type Updatedat3 = string
/**
 * @maxItems 10000
 */
export type Messages1 = ImportMessage[]
export type Conversationid2 = string
export type Reason = ("exists_with_different_data" | "invalid_parent" | "invalid_leaf" | "duplicate_message")
export type Conflicts = ImportConflict[]
export type Draftsimported = number
export type Imported = string[]
export type Skipped = string[]
export type MaxContinuations = number
export type MaxMessageChars = number
export type MaxResponseChars = number
export type MaxStreamBytes = number
export type StreamIdleTimeoutMs = number
export type StreamTimeoutMs = number
export type Assistantmessageid = (string | null)
export type Attempt = number
export type Continuationcount2 = number
export type Conversationid3 = string
export type Generationid1 = string
export type Inputmessageid = string
/**
 * @minItems 1
 * @maxItems 100
 */
export type Messages2 = [LLMMessage, ...(LLMMessage)[]]
export type Content2 = string
export type Role2 = ("user" | "assistant")
export type Modelid2 = string
export type Operation = ("generate" | "continue")
export type Seq1 = number
export type Type1 = "response.completed"
export type Id4 = (string | null)
export type Title2 = (string | null)
export type Conversations1 = ConversationResponse[]
export type Hasmore1 = boolean
export type Nextcursor1 = (string | null)
export type Conversationid4 = string
export type Firstmessage = string
export type Inputmessageid1 = string
export type Modelid3 = string
export type Conversationid5 = string
export type Inputmessageid2 = string
export type Title3 = string
export type Activeleafmessageid2 = (string | null)
export type Archived = (boolean | null)
export type Title4 = (string | null)
export type Version2 = number
export type Delta = string
export type Seq2 = number
export type Type2 = "response.output_text.delta"
export type Content3 = string
export type Key = string
export type Updatedat4 = string
export type Drafts1 = DraftResponse[]
export type Content4 = string
export type Code = string
export type Message = string
export type RequestId = string
export type Evidence = ("DOCUMENTED" | "VERIFIED" | "UNKNOWN")
export type Code1 = string
export type Message1 = string
export type Seq3 = number
export type Type3 = "response.failed"
export type Location = (string | number)[]
export type Message2 = string
export type ErrorType = string
export type Detail = ValidationError[]
export type Service = "noris-ai"
export type Status2 = "ok"
export type Version3 = string
export type Reason1 = "output_limit"
export type Seq4 = number
export type Type4 = "response.incomplete"
export type Available = boolean
export type ContextWindow = number
export type AsOf = (string | null)
export type CachedInputPointsPerMillion = (number | null)
export type InputPointsPerMillion = (number | null)
export type OutputPointsPerMillion = (number | null)
export type Source = string
export type Description = string
export type DocumentedContextWindow = (number | null)
export type Id5 = string
export type Lifecycle = ("LTS" | "PRODUCTIVE" | "EXPERIMENTAL" | "DEPRECATED" | "UNKNOWN")
export type MaxOutputTokens = number
export type Name = string
export type Provider = (string | null)
export type ProviderContextWindow = (number | null)
export type ProviderLimitEvidence = (string | null)
export type ProviderMaxOutputTokens = number
export type Reasoning = (boolean | null)
export type ReasoningEffort = (string | null)
export type ReasoningEfforts = string[]
export type ReasoningParameter = (("reasoning_effort" | "chat_template_kwargs") | null)
export type ReasoningReserveTokens = number
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
export type Completetree = boolean
export type Hasmore2 = boolean
export type Messages3 = MessageResponse[]
export type Nextcursor2 = (string | null)
export type DefaultModel = (string | null)
export type ErrorCode = (string | null)
export type ExpiresInSeconds = number
export type FetchedAt = (string | null)
export type Models = LLMModel[]
export type RegistryVersion = string
export type Status3 = ("fresh" | "stale")
export type ModelCategory = ("CHAT" | "REASONING" | "VISION" | "EMBEDDING" | "RERANKING" | "UNKNOWN")
export type Activeconversationid1 = (string | null)
export type Modelid4 = (string | null)
export type Activeconversationid2 = (string | null)
export type Modelid5 = (string | null)
export type Status4 = "ready"
export type Seq5 = number
export type Type5 = "response.started"
export type Expiresinseconds = number
export type Ticketid = string

export interface ApiSchemas {
  ActivePathResponse: ActivePathResponse
  CancelledEvent: CancelledEvent
  ChatImportRequest: ChatImportRequest
  ChatImportResponse: ChatImportResponse
  ChatLimits: ChatLimits
  ChatRequest: ChatRequest
  CompletedEvent: CompletedEvent
  ConversationCreate: ConversationCreate
  ConversationListResponse: ConversationListResponse
  ConversationResponse: ConversationResponse
  ConversationTitleRequest: ConversationTitleRequest
  ConversationTitleResponse: ConversationTitleResponse
  ConversationUpdate: ConversationUpdate
  DeltaEvent: DeltaEvent
  DraftListResponse: DraftListResponse
  DraftResponse: DraftResponse
  DraftUpdate: DraftUpdate
  ErrorDetail: ErrorDetail
  ErrorResponse: ErrorResponse
  Evidence: Evidence
  FailedEvent: FailedEvent
  HTTPValidationError: HTTPValidationError
  HealthResponse: HealthResponse
  ImportConflict: ImportConflict
  ImportConversation: ImportConversation
  ImportMessage: ImportMessage
  IncompleteEvent: IncompleteEvent
  LLMMessage: LLMMessage
  LLMModel: LLMModel
  MessageListResponse: MessageListResponse
  MessageResponse: MessageResponse
  ModelCatalog: ModelCatalog
  ModelCategory: ModelCategory
  ModelCost: ModelCost
  PreferencesResponse: PreferencesResponse
  PreferencesUpdate: PreferencesUpdate
  ReadinessResponse: ReadinessResponse
  StartedEvent: StartedEvent
  TicketResponse: TicketResponse
  TimeoutPolicy: TimeoutPolicy
  ValidationError: ValidationError
  VariantSummary: VariantSummary
}
export interface ActivePathResponse {
  boundaryParentId?: Boundaryparentid
  conversation: ConversationResponse
  hasMore?: Hasmore
  leafMessageId: Leafmessageid
  messages: Messages
  nextCursor?: Nextcursor
  variants: Variants
}
export interface ConversationResponse {
  activeLeafMessageId: Activeleafmessageid
  archivedAt: Archivedat
  createdAt: Createdat
  id: Id
  lastMessageAt: Lastmessageat
  title: Title
  titleSource: Titlesource
  updatedAt: Updatedat
  version: Version
}
export interface MessageResponse {
  content: Content
  continuationCount?: Continuationcount
  conversationId: Conversationid
  createdAt: Createdat1
  editedFromMessageId: Editedfrommessageid
  errorCode?: Errorcode
  errorMessage?: Errormessage
  generationId: Generationid
  id: Id1
  modelId: Modelid
  parentMessageId: Parentmessageid
  role: Role
  status: Status
  updatedAt: Updatedat1
}
export interface VariantSummary {
  index: Index
  messageId: Messageid
  nextMessageId: Nextmessageid
  previousMessageId: Previousmessageid
  total: Total
}
export interface CancelledEvent {
  seq: Seq
  type?: Type
}
export interface ChatImportRequest {
  activeConversationId?: Activeconversationid
  conversations: Conversations
  drafts?: Drafts
  messages: Messages1
}
export interface ImportConversation {
  activeLeafMessageId?: Activeleafmessageid1
  archivedAt?: Archivedat1
  createdAt: Createdat2
  id: Id2
  title: Title1
  titleSource: Titlesource1
  updatedAt: Updatedat2
  version?: Version1
}
export interface Drafts {
  [k: string]: string
}
export interface ImportMessage {
  content: Content1
  continuationCount?: Continuationcount1
  conversationId: Conversationid1
  createdAt: Createdat3
  editedFromMessageId?: Editedfrommessageid1
  errorCode?: Errorcode1
  errorMessage?: Errormessage1
  id: Id3
  modelId?: Modelid1
  parentMessageId?: Parentmessageid1
  role: Role1
  status: Status1
  updatedAt: Updatedat3
}
export interface ChatImportResponse {
  conflicts: Conflicts
  draftsImported: Draftsimported
  imported: Imported
  skipped: Skipped
}
export interface ImportConflict {
  conversationId: Conversationid2
  reason: Reason
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
  continuationCount?: Continuationcount2
  conversationId: Conversationid3
  generationId: Generationid1
  inputMessageId: Inputmessageid
  messages: Messages2
  modelId: Modelid2
  operation?: Operation
}
export interface LLMMessage {
  content: Content2
  role: Role2
}
export interface CompletedEvent {
  seq: Seq1
  type?: Type1
}
export interface ConversationCreate {
  id?: Id4
  title?: Title2
}
export interface ConversationListResponse {
  conversations: Conversations1
  hasMore?: Hasmore1
  nextCursor?: Nextcursor1
}
export interface ConversationTitleRequest {
  conversationId: Conversationid4
  firstMessage: Firstmessage
  inputMessageId: Inputmessageid1
  modelId: Modelid3
}
export interface ConversationTitleResponse {
  conversationId: Conversationid5
  inputMessageId: Inputmessageid2
  title: Title3
}
export interface ConversationUpdate {
  activeLeafMessageId?: Activeleafmessageid2
  archived?: Archived
  title?: Title4
  version: Version2
}
export interface DeltaEvent {
  delta: Delta
  seq: Seq2
  type?: Type2
}
export interface DraftListResponse {
  drafts: Drafts1
}
export interface DraftResponse {
  content: Content3
  key: Key
  updatedAt: Updatedat4
}
export interface DraftUpdate {
  content: Content4
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
export interface HTTPValidationError {
  detail?: Detail
  [k: string]: unknown
}
export interface ValidationError {
  ctx?: Context
  input?: Input
  loc: Location
  msg: Message2
  type: ErrorType
  [k: string]: unknown
}
export interface Context {
  [k: string]: unknown
}
export interface Input {
  [k: string]: unknown
}
export interface HealthResponse {
  service?: Service
  status?: Status2
  version: Version3
}
export interface IncompleteEvent {
  reason?: Reason1
  seq: Seq4
  type?: Type4
}
export interface LLMModel {
  available?: Available
  category?: ("CHAT" | "REASONING" | "VISION" | "EMBEDDING" | "RERANKING" | "UNKNOWN")
  context_window?: ContextWindow
  cost?: ModelCost
  description?: Description
  documented_context_window?: DocumentedContextWindow
  evidence?: Evidence1
  id: Id5
  lifecycle?: Lifecycle
  max_output_tokens?: MaxOutputTokens
  name: Name
  provider?: Provider
  provider_context_window?: ProviderContextWindow
  provider_limit_evidence?: ProviderLimitEvidence
  provider_max_output_tokens?: ProviderMaxOutputTokens
  reasoning?: Reasoning
  reasoning_effort?: ReasoningEffort
  reasoning_efforts?: ReasoningEfforts
  reasoning_parameter?: ReasoningParameter
  reasoning_reserve_tokens?: ReasoningReserveTokens
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
export interface MessageListResponse {
  completeTree?: Completetree
  hasMore?: Hasmore2
  messages: Messages3
  nextCursor?: Nextcursor2
}
export interface ModelCatalog {
  default_model: DefaultModel
  error_code?: ErrorCode
  expires_in_seconds?: ExpiresInSeconds
  fetched_at?: FetchedAt
  limits: ChatLimits
  models: Models
  registry_version?: RegistryVersion
  status?: Status3
}
export interface PreferencesResponse {
  activeConversationId: Activeconversationid1
  modelId: Modelid4
}
export interface PreferencesUpdate {
  activeConversationId?: Activeconversationid2
  modelId?: Modelid5
}
export interface ReadinessResponse {
  status?: Status4
}
export interface StartedEvent {
  seq: Seq5
  type?: Type5
}
export interface TicketResponse {
  expiresInSeconds: Expiresinseconds
  ticketId: Ticketid
}

export interface ApiPaths {
  "/api/v1/chat/drafts": {
    get: {
      parameters: {
        query: {
          "keys"?: (string)[] | null
        }
      }
      responses: {
      200: ApiSchemas["DraftListResponse"]
      400: ApiSchemas["ErrorResponse"]
      401: ApiSchemas["ErrorResponse"]
      403: ApiSchemas["ErrorResponse"]
      404: ApiSchemas["ErrorResponse"]
      409: ApiSchemas["ErrorResponse"]
      413: ApiSchemas["ErrorResponse"]
      422: ApiSchemas["ErrorResponse"]
      500: ApiSchemas["ErrorResponse"]
      503: ApiSchemas["ErrorResponse"]
    } }
  }
  "/api/v1/chat/drafts/new": {
    put: {
      requestBody: ApiSchemas["DraftUpdate"]
      responses: {
      200: ApiSchemas["DraftResponse"]
      422: ApiSchemas["HTTPValidationError"]
    } }
  }
  "/api/v1/chat/preferences": {
    get: {
      responses: {
      200: ApiSchemas["PreferencesResponse"]
      400: ApiSchemas["ErrorResponse"]
      401: ApiSchemas["ErrorResponse"]
      403: ApiSchemas["ErrorResponse"]
      404: ApiSchemas["ErrorResponse"]
      409: ApiSchemas["ErrorResponse"]
      413: ApiSchemas["ErrorResponse"]
      422: ApiSchemas["ErrorResponse"]
      500: ApiSchemas["ErrorResponse"]
      503: ApiSchemas["ErrorResponse"]
    } }
    put: {
      requestBody: ApiSchemas["PreferencesUpdate"]
      responses: {
      200: ApiSchemas["PreferencesResponse"]
      400: ApiSchemas["ErrorResponse"]
      401: ApiSchemas["ErrorResponse"]
      403: ApiSchemas["ErrorResponse"]
      404: ApiSchemas["ErrorResponse"]
      409: ApiSchemas["ErrorResponse"]
      413: ApiSchemas["ErrorResponse"]
      422: ApiSchemas["ErrorResponse"]
      500: ApiSchemas["ErrorResponse"]
      503: ApiSchemas["ErrorResponse"]
    } }
  }
  "/api/v1/chat/ws-ticket": {
    post: {
      responses: {
      200: ApiSchemas["TicketResponse"]
    } }
  }
  "/api/v1/conversations": {
    get: {
      parameters: {
        query: {
          "archived"?: boolean
          "archiveOnly"?: boolean
          "limit"?: number
          "cursor"?: string | null
          "q"?: string
        }
      }
      responses: {
      200: ApiSchemas["ConversationListResponse"]
      400: ApiSchemas["ErrorResponse"]
      401: ApiSchemas["ErrorResponse"]
      403: ApiSchemas["ErrorResponse"]
      404: ApiSchemas["ErrorResponse"]
      409: ApiSchemas["ErrorResponse"]
      413: ApiSchemas["ErrorResponse"]
      422: ApiSchemas["ErrorResponse"]
      500: ApiSchemas["ErrorResponse"]
      503: ApiSchemas["ErrorResponse"]
    } }
    post: {
      requestBody: ApiSchemas["ConversationCreate"]
      responses: {
      201: ApiSchemas["ConversationResponse"]
      400: ApiSchemas["ErrorResponse"]
      401: ApiSchemas["ErrorResponse"]
      403: ApiSchemas["ErrorResponse"]
      404: ApiSchemas["ErrorResponse"]
      409: ApiSchemas["ErrorResponse"]
      413: ApiSchemas["ErrorResponse"]
      422: ApiSchemas["ErrorResponse"]
      500: ApiSchemas["ErrorResponse"]
      503: ApiSchemas["ErrorResponse"]
    } }
  }
  "/api/v1/conversations/import": {
    post: {
      requestBody: ApiSchemas["ChatImportRequest"]
      responses: {
      200: ApiSchemas["ChatImportResponse"]
      400: ApiSchemas["ErrorResponse"]
      401: ApiSchemas["ErrorResponse"]
      403: ApiSchemas["ErrorResponse"]
      404: ApiSchemas["ErrorResponse"]
      409: ApiSchemas["ErrorResponse"]
      413: ApiSchemas["ErrorResponse"]
      422: ApiSchemas["ErrorResponse"]
      500: ApiSchemas["ErrorResponse"]
      503: ApiSchemas["ErrorResponse"]
    } }
  }
  "/api/v1/conversations/{conversation_id}": {
    delete: {
      parameters: {
        path: {
          "conversation_id": string
        }
      }
      responses: {
      204: void
      400: ApiSchemas["ErrorResponse"]
      401: ApiSchemas["ErrorResponse"]
      403: ApiSchemas["ErrorResponse"]
      404: ApiSchemas["ErrorResponse"]
      409: ApiSchemas["ErrorResponse"]
      413: ApiSchemas["ErrorResponse"]
      422: ApiSchemas["ErrorResponse"]
      500: ApiSchemas["ErrorResponse"]
      503: ApiSchemas["ErrorResponse"]
    } }
    get: {
      parameters: {
        path: {
          "conversation_id": string
        }
      }
      responses: {
      200: ApiSchemas["ConversationResponse"]
      400: ApiSchemas["ErrorResponse"]
      401: ApiSchemas["ErrorResponse"]
      403: ApiSchemas["ErrorResponse"]
      404: ApiSchemas["ErrorResponse"]
      409: ApiSchemas["ErrorResponse"]
      413: ApiSchemas["ErrorResponse"]
      422: ApiSchemas["ErrorResponse"]
      500: ApiSchemas["ErrorResponse"]
      503: ApiSchemas["ErrorResponse"]
    } }
    patch: {
      parameters: {
        path: {
          "conversation_id": string
        }
      }
      requestBody: ApiSchemas["ConversationUpdate"]
      responses: {
      200: ApiSchemas["ConversationResponse"]
      400: ApiSchemas["ErrorResponse"]
      401: ApiSchemas["ErrorResponse"]
      403: ApiSchemas["ErrorResponse"]
      404: ApiSchemas["ErrorResponse"]
      409: ApiSchemas["ErrorResponse"]
      413: ApiSchemas["ErrorResponse"]
      422: ApiSchemas["ErrorResponse"]
      500: ApiSchemas["ErrorResponse"]
      503: ApiSchemas["ErrorResponse"]
    } }
  }
  "/api/v1/conversations/{conversation_id}/active-path": {
    get: {
      parameters: {
        path: {
          "conversation_id": string
        }
        query: {
          "limit"?: number
          "cursor"?: string | null
          "messageId"?: string | null
          "preferredLeafId"?: string | null
          "beforeMessageId"?: string | null
        }
      }
      responses: {
      200: ApiSchemas["ActivePathResponse"]
      400: ApiSchemas["ErrorResponse"]
      401: ApiSchemas["ErrorResponse"]
      403: ApiSchemas["ErrorResponse"]
      404: ApiSchemas["ErrorResponse"]
      409: ApiSchemas["ErrorResponse"]
      413: ApiSchemas["ErrorResponse"]
      422: ApiSchemas["ErrorResponse"]
      500: ApiSchemas["ErrorResponse"]
      503: ApiSchemas["ErrorResponse"]
    } }
  }
  "/api/v1/conversations/{conversation_id}/draft": {
    put: {
      parameters: {
        path: {
          "conversation_id": string
        }
      }
      requestBody: ApiSchemas["DraftUpdate"]
      responses: {
      200: ApiSchemas["DraftResponse"]
      400: ApiSchemas["ErrorResponse"]
      401: ApiSchemas["ErrorResponse"]
      403: ApiSchemas["ErrorResponse"]
      404: ApiSchemas["ErrorResponse"]
      409: ApiSchemas["ErrorResponse"]
      413: ApiSchemas["ErrorResponse"]
      422: ApiSchemas["ErrorResponse"]
      500: ApiSchemas["ErrorResponse"]
      503: ApiSchemas["ErrorResponse"]
    } }
  }
  "/api/v1/conversations/{conversation_id}/messages": {
    get: {
      parameters: {
        path: {
          "conversation_id": string
        }
        query: {
          "limit"?: number
          "cursor"?: string | null
        }
      }
      responses: {
      200: ApiSchemas["MessageListResponse"]
      400: ApiSchemas["ErrorResponse"]
      401: ApiSchemas["ErrorResponse"]
      403: ApiSchemas["ErrorResponse"]
      404: ApiSchemas["ErrorResponse"]
      409: ApiSchemas["ErrorResponse"]
      413: ApiSchemas["ErrorResponse"]
      422: ApiSchemas["ErrorResponse"]
      500: ApiSchemas["ErrorResponse"]
      503: ApiSchemas["ErrorResponse"]
    } }
  }
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
