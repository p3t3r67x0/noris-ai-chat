/* Generated WebSocket v1 contract. Run pnpm api:generate. */
export type ChatWsEvent = (ConnectedEvent | MessageCreatedEvent | GenerationStartedEvent | GenerationDeltaEvent | GenerationCompletedEvent | GenerationIncompleteEvent | GenerationFailedEvent | GenerationCancelledEvent | GenerationInterruptedEvent | ConversationUpdatedEvent | ConversationDeletedEvent | TitleUpdatedEvent | ResumeAcceptedEvent | ResumeSnapshotEvent | ErrorEvent | HeartbeatEvent | PongEvent | ToolEvent | ToolSnapshotEvent | ResearchStateEvent)
export type Heartbeatseconds = number
export type Type = "chat.connected"
export type Version = 1
export type Conversationid = string
export type Conversationid1 = string
export type Createdat = string
export type Extractionstatus = ("extracted" | "no_text" | "unsupported" | "not_applicable")
export type Id = string
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
export type Conversationid2 = string
export type Createdat1 = string
export type Editedfrommessageid = (string | null)
export type Errorcode = (string | null)
export type Errormessage = (string | null)
export type Generationid = (string | null)
export type Id1 = string
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
export type Title = string
/**
 * @maxItems 6
 */
export type Sources = ResearchSource[]
export type State = ("planning" | "searching" | "selecting" | "fetching" | "grounding" | "generating" | "completed" | "failed" | "cancelled" | "interrupted" | "skipped")
export type Version1 = 1
export type Role = ("user" | "assistant")
export type Status2 = ("pending" | "streaming" | "completed" | "incomplete" | "cancelled" | "failed")
export type Updatedat = string
export type Type1 = "chat.message.created"
export type Version2 = 1
export type Continuationcount1 = number
export type Conversationid3 = string
export type Generationid2 = string
export type Messageid1 = string
export type Modelid1 = string
export type Seq = number
export type Type2 = "chat.generation.started"
export type Version3 = 1
export type Continuationcount2 = number
export type Conversationid4 = string
export type Delta = string
export type Generationid3 = string
export type Messageid2 = string
export type Seq1 = number
export type Type3 = "chat.generation.delta"
export type Version4 = 1
export type Content1 = string
export type Continuationcount3 = number
export type Conversationid5 = string
export type Generationid4 = string
export type Messageid3 = string
export type Researchstate = (("planning" | "searching" | "selecting" | "fetching" | "grounding" | "generating" | "completed" | "failed" | "cancelled" | "interrupted" | "skipped") | null)
export type Seq2 = number
export type Type4 = "chat.generation.completed"
export type Version5 = 1
export type Code = (string | null)
export type Content2 = string
export type Continuationcount4 = number
export type Conversationid6 = string
export type Generationid5 = string
export type Message = (string | null)
export type Messageid4 = string
export type Reason = "output_limit"
export type Researchstate1 = (("planning" | "searching" | "selecting" | "fetching" | "grounding" | "generating" | "completed" | "failed" | "cancelled" | "interrupted" | "skipped") | null)
export type Seq3 = number
export type Type5 = "chat.generation.incomplete"
export type Version6 = 1
export type Code1 = string
export type Content3 = string
export type Continuationcount5 = number
export type Conversationid7 = string
export type Generationid6 = string
export type Message1 = string
export type Messageid5 = string
export type Researchstate2 = (("planning" | "searching" | "selecting" | "fetching" | "grounding" | "generating" | "completed" | "failed" | "cancelled" | "interrupted" | "skipped") | null)
export type Seq4 = number
export type Type6 = "chat.generation.failed"
export type Version7 = 1
export type Content4 = string
export type Continuationcount6 = number
export type Conversationid8 = string
export type Generationid7 = string
export type Messageid6 = string
export type Researchstate3 = (("planning" | "searching" | "selecting" | "fetching" | "grounding" | "generating" | "completed" | "failed" | "cancelled" | "interrupted" | "skipped") | null)
export type Seq5 = number
export type Type7 = "chat.generation.cancelled"
export type Version8 = 1
export type Content5 = string
export type Continuationcount7 = number
export type Conversationid9 = string
export type Generationid8 = string
export type Messageid7 = string
export type Researchstate4 = (("planning" | "searching" | "selecting" | "fetching" | "grounding" | "generating" | "completed" | "failed" | "cancelled" | "interrupted" | "skipped") | null)
export type Seq6 = number
export type Type8 = "chat.generation.interrupted"
export type Version9 = 1
export type Activeleafmessageid = (string | null)
export type Archivedat = (string | null)
export type Conversationmode = ("normal" | "learning")
export type Createdat2 = string
export type Id2 = string
export type Lastmessageat = (string | null)
export type Lifecycle = ("EMPTY" | "STARTED" | "GENERATING" | "FAILED" | "COMPLETED")
export type Pinnedat = (string | null)
export type ReasoningPreference = ("instant" | "medium" | "high" | "very_high" | "pro")
export type Sidebarvisible = boolean
export type Title1 = string
export type Titlesource = ("fallback" | "generated" | "manual")
export type Updatedat1 = string
export type Version10 = number
export type Type9 = "chat.conversation.updated"
export type Version11 = 1
export type Conversationid10 = string
export type Conversationversion = number
export type Type10 = "chat.conversation.deleted"
export type Version12 = 1
export type Conversationid11 = string
export type Title2 = string
export type Titlesource1 = string
export type Type11 = "chat.title.updated"
export type Version13 = 1
export type Generationid9 = string
export type Lastreceivedseq = number
export type Type12 = "chat.resume.accepted"
export type Version14 = 1
export type Code2 = (string | null)
export type Content6 = string
export type Continuationcount8 = number
export type Conversationid12 = string
export type Generationid10 = string
export type Lastsequence = number
export type Message2 = (string | null)
export type Messageid8 = string
export type Researchmode = ("web" | null)
export type Researchstate5 = (("planning" | "searching" | "selecting" | "fetching" | "grounding" | "generating" | "completed" | "failed" | "cancelled" | "interrupted" | "skipped") | null)
export type Status3 = ("queued" | "running" | "completed" | "incomplete" | "cancelled" | "failed" | "interrupted")
export type Type13 = "chat.resume.snapshot"
export type Version15 = 1
export type Code3 = string
export type Message3 = string
export type Requestid = (string | null)
export type Type14 = "chat.error"
export type Version16 = 1
export type Type15 = "chat.heartbeat"
export type Version17 = 1
export type Type16 = "chat.pong"
export type Version18 = 1
export type Conversationid13 = string
export type Eventversion = 1
export type Generationid11 = string
export type Approvalid = string
export type Expiresat = string
export type Inputdigest = string
export type State1 = ("pending" | "approved" | "denied" | "expired")
export type Cancelrequested = boolean
export type Errorcode1 = (("TOOL_UNAVAILABLE" | "TOOL_FORBIDDEN" | "TOOL_INPUT_INVALID" | "TOOL_OUTPUT_INVALID" | "TOOL_NOT_FOUND" | "TOOL_CONFLICT" | "TOOL_STATE_CONFLICT" | "APPROVAL_REQUIRED" | "APPROVAL_EXPIRED" | "BUDGET_LIMIT" | "TOOL_TIMEOUT" | "TOOL_INTERRUPTED" | "TOOL_CANCELLED" | "PROVIDER_RATE_LIMIT" | "PROVIDER_ERROR" | "PROVIDER_OUTCOME_UNKNOWN") | null)
export type Lastsequence1 = number
export type Resultversion = 1
export type Sourcecount = (number | null)
export type Runid = string
export type State2 = ("queued" | "awaiting_approval" | "running" | "succeeded" | "failed" | "cancelled" | "timed_out" | "interrupted" | "outcome_unknown")
export type Toolid = ("web.search.v1" | "web.fetch.v1")
export type Updatedat2 = string
export type Runid1 = string
export type Seq7 = number
export type Timestamp = string
export type Type17 = ("tool.started" | "tool.progress" | "tool.result" | "tool.approval_required" | "tool.completed" | "tool.failed" | "tool.cancelled" | "tool.timed_out")
export type Version19 = 1
export type Conversationid14 = string
export type Eventversion1 = 1
export type Generationid12 = string
export type Lastsequence2 = number
/**
 * @maxItems 16
 */
export type Runs = ToolProjection[]
export type Timestamp1 = string
export type Type18 = "tool.snapshot"
export type Version20 = 1
export type Conversationid15 = string
export type Eventversion2 = 1
export type Generationid13 = string
export type Messageid9 = string
export type Seq8 = number
export type State3 = ("planning" | "searching" | "selecting" | "fetching" | "grounding" | "generating" | "completed" | "failed" | "cancelled" | "interrupted" | "skipped")
export type Type19 = "research.updated"
export type Version21 = 1

export interface ConnectedEvent {
  heartbeatSeconds: Heartbeatseconds
  type: Type
  version: Version
}
export interface MessageCreatedEvent {
  conversationId: Conversationid
  message: MessageResponse
  type: Type1
  version: Version2
}
export interface MessageResponse {
  attachments?: Attachments
  content: Content
  continuationCount?: Continuationcount
  conversationId: Conversationid2
  createdAt: Createdat1
  editedFromMessageId: Editedfrommessageid
  errorCode?: Errorcode
  errorMessage?: Errormessage
  generationId: Generationid
  id: Id1
  modelId: Modelid
  parentMessageId: Parentmessageid
  research?: (ResearchView | null)
  role: Role
  status: Status2
  updatedAt: Updatedat
}
export interface AttachmentResponse {
  conversationId: Conversationid1
  createdAt: Createdat
  extractionStatus: Extractionstatus
  id: Id
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
  title: Title
}
export interface GenerationStartedEvent {
  continuationCount: Continuationcount1
  conversationId: Conversationid3
  generationId: Generationid2
  messageId: Messageid1
  modelId: Modelid1
  seq: Seq
  type: Type2
  version: Version3
}
export interface GenerationDeltaEvent {
  continuationCount: Continuationcount2
  conversationId: Conversationid4
  delta: Delta
  generationId: Generationid3
  messageId: Messageid2
  seq: Seq1
  type: Type3
  version: Version4
}
export interface GenerationCompletedEvent {
  content: Content1
  continuationCount: Continuationcount3
  conversationId: Conversationid5
  generationId: Generationid4
  messageId: Messageid3
  researchState: Researchstate
  seq: Seq2
  type: Type4
  version: Version5
}
export interface GenerationIncompleteEvent {
  code: Code
  content: Content2
  continuationCount: Continuationcount4
  conversationId: Conversationid6
  generationId: Generationid5
  message: Message
  messageId: Messageid4
  reason: Reason
  researchState: Researchstate1
  seq: Seq3
  type: Type5
  version: Version6
}
export interface GenerationFailedEvent {
  code: Code1
  content: Content3
  continuationCount: Continuationcount5
  conversationId: Conversationid7
  generationId: Generationid6
  message: Message1
  messageId: Messageid5
  researchState: Researchstate2
  seq: Seq4
  type: Type6
  version: Version7
}
export interface GenerationCancelledEvent {
  content: Content4
  continuationCount: Continuationcount6
  conversationId: Conversationid8
  generationId: Generationid7
  messageId: Messageid6
  researchState: Researchstate3
  seq: Seq5
  type: Type7
  version: Version8
}
export interface GenerationInterruptedEvent {
  content: Content5
  continuationCount: Continuationcount7
  conversationId: Conversationid9
  generationId: Generationid8
  messageId: Messageid7
  researchState: Researchstate4
  seq: Seq6
  type: Type8
  version: Version9
}
export interface ConversationUpdatedEvent {
  conversation: ConversationResponse
  type: Type9
  version: Version11
}
export interface ConversationResponse {
  activeLeafMessageId: Activeleafmessageid
  archivedAt: Archivedat
  conversationMode?: Conversationmode
  createdAt: Createdat2
  id: Id2
  lastMessageAt: Lastmessageat
  lifecycle?: Lifecycle
  pinnedAt?: Pinnedat
  reasoningPreference?: (ReasoningPreference | null)
  sidebarVisible?: Sidebarvisible
  title: Title1
  titleSource: Titlesource
  updatedAt: Updatedat1
  version: Version10
}
export interface ConversationDeletedEvent {
  conversationId: Conversationid10
  conversationVersion: Conversationversion
  type: Type10
  version: Version12
}
export interface TitleUpdatedEvent {
  conversationId: Conversationid11
  title: Title2
  titleSource: Titlesource1
  type: Type11
  version: Version13
}
export interface ResumeAcceptedEvent {
  generationId: Generationid9
  lastReceivedSeq: Lastreceivedseq
  type: Type12
  version: Version14
}
export interface ResumeSnapshotEvent {
  code: Code2
  content: Content6
  continuationCount: Continuationcount8
  conversationId: Conversationid12
  generationId: Generationid10
  lastSequence: Lastsequence
  message: Message2
  messageId: Messageid8
  researchMode: Researchmode
  researchState: Researchstate5
  status: Status3
  type: Type13
  version: Version15
}
export interface ErrorEvent {
  code: Code3
  message: Message3
  requestId: Requestid
  type: Type14
  version: Version16
}
export interface HeartbeatEvent {
  type: Type15
  version: Version17
}
export interface PongEvent {
  type: Type16
  version: Version18
}
export interface ToolEvent {
  conversationId: Conversationid13
  eventVersion: Eventversion
  generationId: Generationid11
  payload: ToolProjection
  runId: Runid1
  seq: Seq7
  timestamp: Timestamp
  type: Type17
  version: Version19
}
export interface ToolProjection {
  approval: (ToolApprovalProjection | null)
  cancelRequested: Cancelrequested
  errorCode: Errorcode1
  lastSequence: Lastsequence1
  result: (ToolResultReference | null)
  runId: Runid
  state: State2
  toolId: Toolid
  updatedAt: Updatedat2
}
export interface ToolApprovalProjection {
  approvalId: Approvalid
  expiresAt: Expiresat
  inputDigest: Inputdigest
  state: State1
}
export interface ToolResultReference {
  resultVersion: Resultversion
  sourceCount: Sourcecount
}
export interface ToolSnapshotEvent {
  conversationId: Conversationid14
  eventVersion: Eventversion1
  generationId: Generationid12
  lastSequence: Lastsequence2
  runs: Runs
  timestamp: Timestamp1
  type: Type18
  version: Version20
}
export interface ResearchStateEvent {
  conversationId: Conversationid15
  eventVersion: Eventversion2
  generationId: Generationid13
  messageId: Messageid9
  seq: Seq8
  state: State3
  type: Type19
  version: Version21
}
