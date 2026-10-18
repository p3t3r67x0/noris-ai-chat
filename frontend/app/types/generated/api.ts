/* Generated from backend OpenAPI. Run pnpm api:generate. Do not edit. */
export type Boundaryparentid = (string | null)
export type Activeleafmessageid = (string | null)
export type Archivedat = (string | null)
export type Conversationmode = ("normal" | "learning")
export type Createdat = string
export type Id = string
export type Lastmessageat = (string | null)
export type Lifecycle = ("EMPTY" | "STARTED" | "GENERATING" | "FAILED" | "COMPLETED")
export type Pinnedat = (string | null)
export type ReasoningPreference = ("instant" | "medium" | "high" | "very_high" | "pro")
export type Sidebarvisible = boolean
export type Title = string
export type Titlesource = ("fallback" | "generated" | "manual")
export type Updatedat = string
export type Version = number
export type Hasmore = boolean
export type Leafmessageid = (string | null)
export type Conversationid = string
export type Createdat1 = string
export type Extractionstatus = ("extracted" | "no_text" | "unsupported" | "not_applicable")
export type Id1 = string
export type Messageid = (string | null)
export type Mimetype = string
export type Modelusable = boolean
export type Originalfilename = string
export type Sha256 = string
export type Sizebytes = number
export type Status = ("ready" | "stored")
export type Sourceconversationid = string
export type Sourcemessageid = string
export type Text = string
export type Attachments = AttachmentResponse[]
export type Content = string
export type Continuationcount = number
export type Conversationid1 = string
export type Createdat2 = string
export type Editedfrommessageid = (string | null)
export type Errorcode = (string | null)
export type Errormessage = (string | null)
export type Generationid = (string | null)
export type Id2 = string
export type Modelid = (string | null)
export type Parentmessageid = (string | null)
export type ClaimSupport = "unverified"
export type End = number
export type Marker = string
export type Start = number
/**
 * @maxItems 256
 */
export type Citations = CitationReference[]
export type Claimsupport = "unverified"
export type Generationid1 = string
export type Inherited = boolean
export type Mode = "web"
export type Modelresponseobserved = boolean
export type Sourcegenerationid = string
export type Contentdigest = (string | null)
export type Excerpt = (string | null)
export type Fetchrunid = string
export type Fetchedat = (string | null)
export type Finalurl = (string | null)
export type Marker1 = (string | null)
export type Originalurl = string
export type Searchrunid = string
export type Sourceid = string
export type Status1 = ("context_prepared" | "unavailable")
export type Title1 = string
/**
 * @maxItems 6
 */
export type Sources = ResearchSource[]
export type State = ("planning" | "searching" | "selecting" | "fetching" | "grounding" | "generating" | "completed" | "failed" | "cancelled" | "interrupted" | "skipped")
export type Version1 = 1
export type Role = ("user" | "assistant")
export type Status2 = ("pending" | "streaming" | "completed" | "incomplete" | "cancelled" | "failed")
export type Updatedat1 = string
export type Messages = MessageResponse[]
export type Nextcursor = (string | null)
/**
 * @maxItems 50
 */
export type Toolgenerationids = string[]
export type Index = number
export type Messageid1 = string
export type Nextmessageid = (string | null)
export type Previousmessageid = (string | null)
export type Total = number
export type Variants = VariantSummary[]
export type Maxfilebytes = number
export type Maxfiles = number
export type Maxreferencechars = number
export type Mimetypes = string[]
export type Ownerquotabytes = number
export type Visionsupported = boolean
export type Attachments1 = AttachmentResponse[]
export type Seq = number
export type Type = "response.cancelled"
export type Available = boolean
export type ChatApproved = boolean
export type ContextWindow = number
export type AsOf = (string | null)
export type CachedInputPointsPerMillion = (number | null)
export type CachedInputUsdPerMillion = (string | null)
export type Currency = ("USD" | null)
export type DiscountApplied = boolean
export type DiscountToUser = (string | null)
export type InputPointsPerMillion = (number | null)
export type InputUsdPerMillion = (string | null)
export type IsFree = (boolean | null)
export type OutputPointsPerMillion = (number | null)
export type OutputUsdPerMillion = (string | null)
export type Source = string
export type Description = string
export type DocumentedContextWindow = (number | null)
export type EffectiveContextWindow = (number | null)
export type EffectiveMaxOutputTokens = (number | null)
export type EstimatedMaxCostUsd = (string | null)
export type Evidence1 = ("DOCUMENTED" | "VERIFIED" | "UNKNOWN")
export type HuggingFaceId = (string | null)
export type Id3 = string
export type InputModalities = string[]
export type IsReady = (boolean | null)
export type Lifecycle1 = ("LTS" | "PRODUCTIVE" | "EXPERIMENTAL" | "DEPRECATED" | "UNKNOWN")
export type MaxOutputTokens = number
export type Name = string
export type OutputModalities = string[]
export type Provider = (string | null)
export type ProviderContextWindow = (number | null)
export type ProviderCreatedAt = (string | null)
export type ProviderDatacenters = string[]
export type ProviderLimitEvidence = (string | null)
export type ProviderMaxOutputTokens = (number | null)
export type ProviderName = (string | null)
export type ProviderSchemaVersion = (string | null)
export type Reasoning = (boolean | null)
export type ReasoningEffort = (string | null)
export type ReasoningEfforts = string[]
export type ReasoningParameter = (("reasoning_effort" | "chat_template_kwargs") | null)
export type ReasoningPreferences = ReasoningPreference[]
export type ReasoningReserveTokens = number
export type ReleasedAt = (string | null)
export type ResearchEligible = boolean
export type Sources1 = string[]
export type Streaming = boolean
export type SupportedOutputTokens = (number | null)
export type ReadSeconds = number
export type TotalSeconds = number
export type TokenLimitParameter = (("max_tokens" | "max_completion_tokens") | null)
export type ToolCalling = (boolean | null)
export type VerifiedMaxOutputTokens = (number | null)
export type VerifiedOutputEvidence = (string | null)
export type Virtual = boolean
export type Vision = (boolean | null)
export type Activeconversationid = (string | null)
export type Activeleafmessageid1 = (string | null)
export type Archivedat1 = (string | null)
export type Conversationmode1 = ("normal" | "learning")
export type Createdat3 = string
export type Id4 = string
export type Pinnedat1 = (string | null)
export type Title2 = string
export type Titlesource1 = ("fallback" | "generated" | "manual")
export type Updatedat2 = string
export type Version2 = number
/**
 * @maxItems 500
 */
export type Conversations = ImportConversation[]
export type Content1 = string
export type Continuationcount1 = number
export type Conversationid2 = string
export type Createdat4 = string
export type Editedfrommessageid1 = (string | null)
export type Errorcode1 = (string | null)
export type Errormessage1 = (string | null)
export type Id5 = string
export type Modelid1 = (string | null)
export type Parentmessageid1 = (string | null)
export type Role1 = ("user" | "assistant")
export type Status3 = ("pending" | "streaming" | "completed" | "incomplete" | "cancelled" | "failed")
export type Updatedat3 = string
/**
 * @maxItems 10000
 */
export type Messages1 = ImportMessage[]
export type Conversationid3 = string
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
export type Conversationid4 = string
export type Generationid2 = string
export type Inputmessageid = string
export type Content2 = string
export type Role2 = ("user" | "assistant")
/**
 * @minItems 1
 * @maxItems 100
 */
export type Messages2 = LLMMessage[]
export type Modelid2 = string
export type Operation = ("generate" | "continue")
export type Seq1 = number
export type Type1 = "response.completed"
export type Conversationmode2 = ("normal" | "learning")
export type Id6 = (string | null)
export type Prepared = boolean
export type Title3 = (string | null)
export type Conversations1 = ConversationResponse[]
export type Hasmore1 = boolean
export type Conversationid5 = string
export type Excerpt1 = string
export type Messageid2 = string
export type Matches = ConversationSearchMatch[]
export type Nextcursor1 = (string | null)
export type Conversationid6 = string
export type Firstmessage = string
export type Inputmessageid1 = string
export type Modelid3 = string
export type Conversationid7 = string
export type Inputmessageid2 = string
export type Title4 = string
export type Activeleafmessageid2 = (string | null)
export type Archived = (boolean | null)
export type Conversationmode3 = (("normal" | "learning") | null)
export type Pinned = (boolean | null)
export type Title5 = (string | null)
export type Version3 = number
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
export type Code1 = string
export type Message1 = string
export type Seq3 = number
export type Type3 = "response.failed"
export type Location = (string | number)[]
export type Message2 = string
export type ErrorType = string
export type Detail = ValidationError[]
export type Service = "noris-ai"
export type Status4 = "ok"
export type Version4 = string
export type Reason1 = "output_limit"
export type Seq4 = number
export type Type4 = "response.incomplete"
export type Completetree = boolean
export type Hasmore2 = boolean
export type Messages3 = MessageResponse[]
export type Nextcursor2 = (string | null)
export type DefaultModel = (string | null)
export type ErrorCode = (string | null)
export type ExpiresInSeconds = number
export type FetchedAt = (string | null)
export type Models = CatalogLLMModel[]
export type RegistryVersion = string
export type Status5 = ("fresh" | "stale")
export type ModelCategory = ("CHAT" | "REASONING" | "VISION" | "EMBEDDING" | "RERANKING" | "UNKNOWN")
export type Activeconversationid1 = (string | null)
export type Modelid4 = (string | null)
export type Activeconversationid2 = (string | null)
export type Modelid5 = (string | null)
export type Status6 = "ready"
export type Available1 = boolean
export type Reasoncode = (string | null)
export type Version5 = 1
export type ConfigVersion = string
export type FetchedAt1 = string
export type Partial = boolean
export type Provider1 = ("searxng" | "brave")
export type PublishedAt = (string | null)
export type Snippet = string
export type SourceId = string
export type Title6 = string
export type Url = string
/**
 * @maxItems 8
 */
export type Sources2 = SearchSource[]
/**
 * @maxItems 10
 */
export type Warnings = string[]
export type Digest = string
export type FetchedAt2 = string
export type FinalUrl = string
export type Mime = ("text/plain" | "text/html")
export type SourceId1 = string
export type Text1 = string
export type Seq5 = number
export type Type5 = "response.started"
export type Conversationid8 = string
export type Sourceconversationid1 = string
export type Sourcemessageid1 = string
export type Text2 = string
export type Expiresinseconds = number
export type Ticketid = string
export type Decision = ("approve" | "deny")
export type Inputdigest = string
export type Requestid = string
export type Configversion = string
export type Currency1 = string
export type Decidedat = (string | null)
export type Expiresat = string
export type Id7 = string
export type Inputdigest1 = string
export type Maxcalls = number
export type Maxcost = string
export type Permissionscope = string
export type Provider2 = string
export type Runid = string
export type Schemaversion = 1
export type State1 = ("pending" | "approved" | "denied" | "expired")
export type Reasoncode1 = (("TOOL_UNAVAILABLE" | "TOOL_FORBIDDEN" | "TOOL_INPUT_INVALID" | "TOOL_OUTPUT_INVALID" | "TOOL_NOT_FOUND" | "TOOL_CONFLICT" | "TOOL_STATE_CONFLICT" | "APPROVAL_REQUIRED" | "APPROVAL_EXPIRED" | "BUDGET_LIMIT" | "TOOL_TIMEOUT" | "TOOL_INTERRUPTED" | "TOOL_CANCELLED" | "PROVIDER_RATE_LIMIT" | "PROVIDER_ERROR" | "PROVIDER_OUTCOME_UNKNOWN") | null)
export type Status7 = ("available" | "unavailable")
export type Toolid = string
export type Features = ToolCapability[]
export type Schemaversion1 = 1
export type Errorcode2 = (("TOOL_UNAVAILABLE" | "TOOL_FORBIDDEN" | "TOOL_INPUT_INVALID" | "TOOL_OUTPUT_INVALID" | "TOOL_NOT_FOUND" | "TOOL_CONFLICT" | "TOOL_STATE_CONFLICT" | "APPROVAL_REQUIRED" | "APPROVAL_EXPIRED" | "BUDGET_LIMIT" | "TOOL_TIMEOUT" | "TOOL_INTERRUPTED" | "TOOL_CANCELLED" | "PROVIDER_RATE_LIMIT" | "PROVIDER_ERROR" | "PROVIDER_OUTCOME_UNKNOWN") | null)
export type Latestresult = (SearchResult | SourceDocument | null)
export type Attempt1 = number
export type CancelRequestedAt = (string | null)
export type ConversationId = string
export type DeadlineAt = string
export type ExecutionDeadlineAt = (string | null)
export type FinishedAt = (string | null)
export type GenerationId = string
export type Id8 = string
export type InputDigest = string
export type InvocationKind = ("web_mode" | "research_step" | "user_action")
export type ParentRunId = (string | null)
export type SchemaVersion = number
export type StartedAt = (string | null)
export type State2 = ("queued" | "awaiting_approval" | "running" | "succeeded" | "failed" | "cancelled" | "timed_out" | "interrupted" | "outcome_unknown")
export type StepKey = string
export type ToolId = string
export type Schemaversion2 = 1

export interface ApiSchemas {
  ActivePathResponse: ActivePathResponse
  AttachmentLimitsResponse: AttachmentLimitsResponse
  AttachmentListResponse: AttachmentListResponse
  AttachmentResponse: AttachmentResponse
  CancelledEvent: CancelledEvent
  CatalogLLMModel: CatalogLLMModel
  ChatImportRequest: ChatImportRequest
  ChatImportResponse: ChatImportResponse
  ChatLimits: ChatLimits
  ChatRequest: ChatRequest
  CitationReference: CitationReference
  CompletedEvent: CompletedEvent
  ConversationCreate: ConversationCreate
  ConversationListResponse: ConversationListResponse
  ConversationResponse: ConversationResponse
  ConversationSearchMatch: ConversationSearchMatch
  ConversationTitleRequest: ConversationTitleRequest
  ConversationTitleResponse: ConversationTitleResponse
  ConversationUpdate: ConversationUpdate
  DeltaEvent: DeltaEvent
  DraftListResponse: DraftListResponse
  DraftResponse: DraftResponse
  DraftUpdate: DraftUpdate
  ErrorDetail: ErrorDetail
  ErrorResponse: ErrorResponse
  Evidence: Evidence1
  FailedEvent: FailedEvent
  HTTPValidationError: HTTPValidationError
  HealthResponse: HealthResponse
  ImportConflict: ImportConflict
  ImportConversation: ImportConversation
  ImportMessage: ImportMessage
  IncompleteEvent: IncompleteEvent
  LLMMessage: LLMMessage
  MessageListResponse: MessageListResponse
  MessageResponse: MessageResponse
  ModelCatalog: ModelCatalog
  ModelCategory: ModelCategory
  ModelCost: ModelCost
  PreferencesResponse: PreferencesResponse
  PreferencesUpdate: PreferencesUpdate
  ReadinessResponse: ReadinessResponse
  ReasoningPreference: ReasoningPreference
  ResearchCapability: ResearchCapability
  ResearchSource: ResearchSource
  ResearchView: ResearchView
  SearchResult: SearchResult
  SearchSource: SearchSource
  SourceDocument: SourceDocument
  StartedEvent: StartedEvent
  TextReference: TextReference
  TextReferenceCreate: TextReferenceCreate
  TicketResponse: TicketResponse
  TimeoutPolicy: TimeoutPolicy
  ToolApprovalDecision: ToolApprovalDecision
  ToolApprovalResponse: ToolApprovalResponse
  ToolCapabilitiesResponse: ToolCapabilitiesResponse
  ToolCapability: ToolCapability
  ToolRunResponse: ToolRunResponse
  ToolRunSnapshot: ToolRunSnapshot
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
  toolGenerationIds?: Toolgenerationids
  variants: Variants
}
export interface ConversationResponse {
  activeLeafMessageId: Activeleafmessageid
  archivedAt: Archivedat
  conversationMode?: Conversationmode
  createdAt: Createdat
  id: Id
  lastMessageAt: Lastmessageat
  lifecycle?: Lifecycle
  pinnedAt?: Pinnedat
  reasoningPreference?: (ReasoningPreference | null)
  sidebarVisible?: Sidebarvisible
  title: Title
  titleSource: Titlesource
  updatedAt: Updatedat
  version: Version
}
export interface MessageResponse {
  attachments?: Attachments
  content: Content
  continuationCount?: Continuationcount
  conversationId: Conversationid1
  createdAt: Createdat2
  editedFromMessageId: Editedfrommessageid
  errorCode?: Errorcode
  errorMessage?: Errormessage
  generationId: Generationid
  id: Id2
  modelId: Modelid
  parentMessageId: Parentmessageid
  research?: (ResearchView | null)
  role: Role
  status: Status2
  updatedAt: Updatedat1
}
export interface AttachmentResponse {
  conversationId: Conversationid
  createdAt: Createdat1
  extractionStatus: Extractionstatus
  id: Id1
  messageId: Messageid
  mimeType: Mimetype
  modelUsable: Modelusable
  originalFilename: Originalfilename
  sha256: Sha256
  sizeBytes: Sizebytes
  status: Status
  textReference?: (TextReference | null)
}
export interface TextReference {
  sourceConversationId: Sourceconversationid
  sourceMessageId: Sourcemessageid
  text: Text
}
export interface ResearchView {
  citations: Citations
  claimSupport: Claimsupport
  generationId: Generationid1
  inherited: Inherited
  mode: Mode
  modelResponseObserved: Modelresponseobserved
  sourceGenerationId: Sourcegenerationid
  sources: Sources
  state: State
  version: Version1
}
export interface CitationReference {
  claim_support?: ClaimSupport
  end: End
  marker: Marker
  start: Start
}
export interface ResearchSource {
  contentDigest: Contentdigest
  excerpt: Excerpt
  fetchRunId: Fetchrunid
  fetchedAt: Fetchedat
  finalUrl: Finalurl
  marker: Marker1
  originalUrl: Originalurl
  searchRunId: Searchrunid
  sourceId: Sourceid
  status: Status1
  title: Title1
}
export interface VariantSummary {
  index: Index
  messageId: Messageid1
  nextMessageId: Nextmessageid
  previousMessageId: Previousmessageid
  total: Total
}
export interface AttachmentLimitsResponse {
  maxFileBytes: Maxfilebytes
  maxFiles: Maxfiles
  maxReferenceChars?: Maxreferencechars
  mimeTypes: Mimetypes
  ownerQuotaBytes: Ownerquotabytes
  visionSupported?: Visionsupported
}
export interface AttachmentListResponse {
  attachments: Attachments1
}
export interface CancelledEvent {
  seq: Seq
  type?: Type
}
/**
 * Read-only catalog projection; derived capability never enters policy input.
 */
export interface CatalogLLMModel {
  available?: Available
  category?: ("CHAT" | "REASONING" | "VISION" | "EMBEDDING" | "RERANKING" | "UNKNOWN")
  chat_approved?: ChatApproved
  context_window?: ContextWindow
  cost?: ModelCost
  description?: Description
  documented_context_window?: DocumentedContextWindow
  effective_context_window?: EffectiveContextWindow
  effective_max_output_tokens?: EffectiveMaxOutputTokens
  estimated_max_cost_usd?: EstimatedMaxCostUsd
  evidence?: Evidence
  hugging_face_id?: HuggingFaceId
  id: Id3
  input_modalities?: InputModalities
  is_ready?: IsReady
  lifecycle?: Lifecycle1
  max_output_tokens?: MaxOutputTokens
  name: Name
  output_modalities?: OutputModalities
  provenance?: Provenance
  provider?: Provider
  provider_compliance?: ProviderCompliance
  provider_context_window?: ProviderContextWindow
  provider_created_at?: ProviderCreatedAt
  provider_datacenters?: ProviderDatacenters
  provider_limit_evidence?: ProviderLimitEvidence
  provider_max_output_tokens?: ProviderMaxOutputTokens
  provider_name?: ProviderName
  provider_schema_version?: ProviderSchemaVersion
  reasoning?: Reasoning
  reasoning_effort?: ReasoningEffort
  reasoning_efforts?: ReasoningEfforts
  reasoning_parameter?: ReasoningParameter
  reasoning_preferences?: ReasoningPreferences
  reasoning_reserve_tokens?: ReasoningReserveTokens
  released_at?: ReleasedAt
  research_eligible: ResearchEligible
  sources?: Sources1
  streaming?: Streaming
  supported_output_tokens?: SupportedOutputTokens
  timeout_policy?: TimeoutPolicy
  token_limit_parameter?: TokenLimitParameter
  tool_calling?: ToolCalling
  verified_max_output_tokens?: VerifiedMaxOutputTokens
  verified_output_evidence?: VerifiedOutputEvidence
  virtual?: Virtual
  vision?: Vision
}
export interface ModelCost {
  as_of?: AsOf
  cached_input_points_per_million?: CachedInputPointsPerMillion
  cached_input_usd_per_million?: CachedInputUsdPerMillion
  currency?: Currency
  discount_applied?: DiscountApplied
  discount_to_user?: DiscountToUser
  evidence?: ("DOCUMENTED" | "VERIFIED" | "UNKNOWN")
  input_points_per_million?: InputPointsPerMillion
  input_usd_per_million?: InputUsdPerMillion
  is_free?: IsFree
  output_points_per_million?: OutputPointsPerMillion
  output_usd_per_million?: OutputUsdPerMillion
  source?: Source
}
export interface Evidence {
  [k: string]: Evidence1
}
export interface Provenance {
  [k: string]: ("PROVIDER" | "LOCAL_POLICY" | "DOCUMENTATION" | "LIVE_TEST" | "UNKNOWN")
}
export interface ProviderCompliance {
  [k: string]: (boolean | null)
}
export interface TimeoutPolicy {
  read_seconds?: ReadSeconds
  total_seconds?: TotalSeconds
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
  conversationMode?: Conversationmode1
  createdAt: Createdat3
  id: Id4
  pinnedAt?: Pinnedat1
  reasoningPreference?: (ReasoningPreference | null)
  title: Title2
  titleSource: Titlesource1
  updatedAt: Updatedat2
  version?: Version2
}
export interface Drafts {
  [k: string]: string
}
export interface ImportMessage {
  content: Content1
  continuationCount?: Continuationcount1
  conversationId: Conversationid2
  createdAt: Createdat4
  editedFromMessageId?: Editedfrommessageid1
  errorCode?: Errorcode1
  errorMessage?: Errormessage1
  id: Id5
  modelId?: Modelid1
  parentMessageId?: Parentmessageid1
  role: Role1
  status: Status3
  updatedAt: Updatedat3
}
export interface ChatImportResponse {
  conflicts: Conflicts
  draftsImported: Draftsimported
  imported: Imported
  skipped: Skipped
}
export interface ImportConflict {
  conversationId: Conversationid3
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
  conversationId: Conversationid4
  generationId: Generationid2
  inputMessageId: Inputmessageid
  messages: Messages2
  modelId: Modelid2
  operation?: Operation
  reasoningPreference?: (ReasoningPreference | null)
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
  conversationMode?: Conversationmode2
  id?: Id6
  prepared?: Prepared
  reasoningPreference?: (ReasoningPreference | null)
  title?: Title3
}
export interface ConversationListResponse {
  conversations: Conversations1
  hasMore?: Hasmore1
  matches?: Matches
  nextCursor?: Nextcursor1
}
export interface ConversationSearchMatch {
  conversationId: Conversationid5
  excerpt: Excerpt1
  messageId: Messageid2
}
export interface ConversationTitleRequest {
  conversationId: Conversationid6
  firstMessage: Firstmessage
  inputMessageId: Inputmessageid1
  modelId: Modelid3
}
export interface ConversationTitleResponse {
  conversationId: Conversationid7
  inputMessageId: Inputmessageid2
  title: Title4
}
export interface ConversationUpdate {
  activeLeafMessageId?: Activeleafmessageid2
  archived?: Archived
  conversationMode?: Conversationmode3
  pinned?: Pinned
  reasoningPreference?: (ReasoningPreference | null)
  title?: Title5
  version: Version3
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
  status?: Status4
  version: Version4
}
export interface IncompleteEvent {
  reason?: Reason1
  seq: Seq4
  type?: Type4
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
  status?: Status5
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
  status?: Status6
}
export interface ResearchCapability {
  available: Available1
  reasonCode: Reasoncode
  version: Version5
}
export interface SearchResult {
  config_version: ConfigVersion
  fetched_at: FetchedAt1
  partial?: Partial
  provider: Provider1
  sources: Sources2
  warnings?: Warnings
}
export interface SearchSource {
  published_at?: PublishedAt
  snippet: Snippet
  source_id: SourceId
  title: Title6
  url: Url
}
export interface SourceDocument {
  digest: Digest
  fetched_at: FetchedAt2
  final_url: FinalUrl
  mime: Mime
  source_id: SourceId1
  text: Text1
}
export interface StartedEvent {
  seq: Seq5
  type?: Type5
}
export interface TextReferenceCreate {
  conversationId: Conversationid8
  sourceConversationId: Sourceconversationid1
  sourceMessageId: Sourcemessageid1
  text: Text2
}
export interface TicketResponse {
  expiresInSeconds: Expiresinseconds
  ticketId: Ticketid
}
export interface ToolApprovalDecision {
  decision: Decision
  inputDigest: Inputdigest
  requestId: Requestid
}
export interface ToolApprovalResponse {
  configVersion: Configversion
  currency: Currency1
  decidedAt: Decidedat
  expiresAt: Expiresat
  id: Id7
  inputDigest: Inputdigest1
  maxCalls: Maxcalls
  maxCost: Maxcost
  permissionScope: Permissionscope
  provider: Provider2
  runId: Runid
  schemaVersion?: Schemaversion
  state: State1
}
export interface ToolCapabilitiesResponse {
  features: Features
  schemaVersion?: Schemaversion1
}
export interface ToolCapability {
  reasonCode?: Reasoncode1
  status: Status7
  toolId: Toolid
}
export interface ToolRunResponse {
  approval: (ToolApprovalResponse | null)
  errorCode: Errorcode2
  latestResult: Latestresult
  run: ToolRunSnapshot
  schemaVersion?: Schemaversion2
}
export interface ToolRunSnapshot {
  attempt: Attempt1
  cancel_requested_at: CancelRequestedAt
  conversation_id: ConversationId
  deadline_at: DeadlineAt
  execution_deadline_at?: ExecutionDeadlineAt
  finished_at: FinishedAt
  generation_id: GenerationId
  id: Id8
  input_digest: InputDigest
  invocation_kind: InvocationKind
  parent_run_id: ParentRunId
  schema_version: SchemaVersion
  started_at: StartedAt
  state: State2
  step_key: StepKey
  tool_id: ToolId
}

export interface ApiPaths {
  "/api/v1/chat/attachments": {
    get: {
      parameters: {
        query: {
          "conversationId": string
        }
      }
      responses: {
      200: ApiSchemas["AttachmentListResponse"]
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
      parameters: {
        query: {
          "conversationId": string
          "filename": string
        }
      }
      requestBody: Blob
      responses: {
      201: ApiSchemas["AttachmentResponse"]
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
  "/api/v1/chat/attachments/limits": {
    get: {
      responses: {
      200: ApiSchemas["AttachmentLimitsResponse"]
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
  "/api/v1/chat/attachments/references": {
    post: {
      requestBody: ApiSchemas["TextReferenceCreate"]
      responses: {
      201: ApiSchemas["AttachmentResponse"]
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
  "/api/v1/chat/attachments/{attachment_id}": {
    delete: {
      parameters: {
        path: {
          "attachment_id": string
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
  }
  "/api/v1/chat/attachments/{attachment_id}/content": {
    get: {
      parameters: {
        path: {
          "attachment_id": string
        }
        query: {
          "preview"?: boolean
        }
      }
      responses: {
      200: Blob
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
  "/api/v1/chat/conversations/{conversation_id}/generations/{generation_id}/research": {
    get: {
      parameters: {
        path: {
          "conversation_id": string
          "generation_id": string
        }
      }
      responses: {
      200: ApiSchemas["ResearchView"] | null
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
  "/api/v1/chat/research/capability": {
    get: {
      responses: {
      200: ApiSchemas["ResearchCapability"]
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
  "/api/v1/chat/tool-approvals/{approval_id}/decision": {
    post: {
      parameters: {
        path: {
          "approval_id": string
        }
      }
      requestBody: ApiSchemas["ToolApprovalDecision"]
      responses: {
      200: ApiSchemas["ToolApprovalResponse"]
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
  "/api/v1/chat/tool-runs/{run_id}": {
    get: {
      parameters: {
        path: {
          "run_id": string
        }
      }
      responses: {
      200: ApiSchemas["ToolRunResponse"]
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
  "/api/v1/chat/tools/capabilities": {
    get: {
      responses: {
      200: ApiSchemas["ToolCapabilitiesResponse"]
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
          "preparedOnly"?: boolean
          "limit"?: number
          "cursor"?: string | null
          "q"?: string
          "pinned"?: boolean | null
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
