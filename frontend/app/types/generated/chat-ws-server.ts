/* Generated WebSocket v1 contract. Run pnpm api:generate. */
export type ChatWsEvent = (ConnectedEvent | MessageCreatedEvent | GenerationStartedEvent | GenerationDeltaEvent | GenerationCompletedEvent | GenerationIncompleteEvent | GenerationFailedEvent | GenerationCancelledEvent | GenerationInterruptedEvent | ConversationUpdatedEvent | TitleUpdatedEvent | ResumeAcceptedEvent | ResumeSnapshotEvent | ErrorEvent | HeartbeatEvent | PongEvent)
export type Heartbeatseconds = number
export type Type = "chat.connected"
export type Version = 1
export type Conversationid = string
export type Content = string
export type Continuationcount = number
export type Conversationid1 = string
export type Createdat = string
export type Editedfrommessageid = (string | null)
export type Errorcode = (string | null)
export type Errormessage = (string | null)
export type Generationid = (string | null)
export type Id = string
export type Modelid = (string | null)
export type Parentmessageid = (string | null)
export type Role = ("user" | "assistant")
export type Status = ("pending" | "streaming" | "completed" | "incomplete" | "cancelled" | "failed")
export type Updatedat = string
export type Type1 = "chat.message.created"
export type Version1 = 1
export type Conversationid2 = string
export type Generationid1 = string
export type Messageid = string
export type Modelid1 = string
export type Seq = number
export type Type2 = "chat.generation.started"
export type Version2 = 1
export type Conversationid3 = string
export type Delta = string
export type Generationid2 = string
export type Messageid1 = string
export type Seq1 = number
export type Type3 = "chat.generation.delta"
export type Version3 = 1
export type Content1 = string
export type Conversationid4 = string
export type Generationid3 = string
export type Messageid2 = string
export type Seq2 = number
export type Type4 = "chat.generation.completed"
export type Version4 = 1
export type Content2 = string
export type Conversationid5 = string
export type Generationid4 = string
export type Messageid3 = string
export type Reason = "output_limit"
export type Seq3 = number
export type Type5 = "chat.generation.incomplete"
export type Version5 = 1
export type Code = string
export type Content3 = string
export type Conversationid6 = string
export type Generationid5 = string
export type Message = string
export type Messageid4 = string
export type Seq4 = number
export type Type6 = "chat.generation.failed"
export type Version6 = 1
export type Content4 = string
export type Conversationid7 = string
export type Generationid6 = string
export type Messageid5 = string
export type Seq5 = number
export type Type7 = "chat.generation.cancelled"
export type Version7 = 1
export type Content5 = string
export type Conversationid8 = string
export type Generationid7 = string
export type Messageid6 = string
export type Seq6 = number
export type Type8 = "chat.generation.interrupted"
export type Version8 = 1
export type Activeleafmessageid = (string | null)
export type Archivedat = (string | null)
export type Createdat1 = string
export type Id1 = string
export type Lastmessageat = (string | null)
export type Title = string
export type Titlesource = ("fallback" | "generated" | "manual")
export type Updatedat1 = string
export type Version9 = number
export type Type9 = "chat.conversation.updated"
export type Version10 = 1
export type Conversationid9 = string
export type Title1 = string
export type Titlesource1 = string
export type Type10 = "chat.title.updated"
export type Version11 = 1
export type Generationid8 = string
export type Lastreceivedseq = number
export type Type11 = "chat.resume.accepted"
export type Version12 = 1
export type Content6 = string
export type Conversationid10 = string
export type Generationid9 = string
export type Lastsequence = number
export type Messageid7 = string
export type Status1 = ("queued" | "running" | "completed" | "incomplete" | "cancelled" | "failed" | "interrupted")
export type Type12 = "chat.resume.snapshot"
export type Version13 = 1
export type Code1 = string
export type Message1 = string
export type Requestid = (string | null)
export type Type13 = "chat.error"
export type Version14 = 1
export type Type14 = "chat.heartbeat"
export type Version15 = 1
export type Type15 = "chat.pong"
export type Version16 = 1

export interface ConnectedEvent {
  heartbeatSeconds: Heartbeatseconds
  type: Type
  version: Version
}
export interface MessageCreatedEvent {
  conversationId: Conversationid
  message: MessageResponse
  type: Type1
  version: Version1
}
export interface MessageResponse {
  content: Content
  continuationCount?: Continuationcount
  conversationId: Conversationid1
  createdAt: Createdat
  editedFromMessageId: Editedfrommessageid
  errorCode?: Errorcode
  errorMessage?: Errormessage
  generationId: Generationid
  id: Id
  modelId: Modelid
  parentMessageId: Parentmessageid
  role: Role
  status: Status
  updatedAt: Updatedat
}
export interface GenerationStartedEvent {
  conversationId: Conversationid2
  generationId: Generationid1
  messageId: Messageid
  modelId: Modelid1
  seq: Seq
  type: Type2
  version: Version2
}
export interface GenerationDeltaEvent {
  conversationId: Conversationid3
  delta: Delta
  generationId: Generationid2
  messageId: Messageid1
  seq: Seq1
  type: Type3
  version: Version3
}
export interface GenerationCompletedEvent {
  content: Content1
  conversationId: Conversationid4
  generationId: Generationid3
  messageId: Messageid2
  seq: Seq2
  type: Type4
  version: Version4
}
export interface GenerationIncompleteEvent {
  content: Content2
  conversationId: Conversationid5
  generationId: Generationid4
  messageId: Messageid3
  reason: Reason
  seq: Seq3
  type: Type5
  version: Version5
}
export interface GenerationFailedEvent {
  code: Code
  content: Content3
  conversationId: Conversationid6
  generationId: Generationid5
  message: Message
  messageId: Messageid4
  seq: Seq4
  type: Type6
  version: Version6
}
export interface GenerationCancelledEvent {
  content: Content4
  conversationId: Conversationid7
  generationId: Generationid6
  messageId: Messageid5
  seq: Seq5
  type: Type7
  version: Version7
}
export interface GenerationInterruptedEvent {
  content: Content5
  conversationId: Conversationid8
  generationId: Generationid7
  messageId: Messageid6
  seq: Seq6
  type: Type8
  version: Version8
}
export interface ConversationUpdatedEvent {
  conversation: ConversationResponse
  type: Type9
  version: Version10
}
export interface ConversationResponse {
  activeLeafMessageId: Activeleafmessageid
  archivedAt: Archivedat
  createdAt: Createdat1
  id: Id1
  lastMessageAt: Lastmessageat
  title: Title
  titleSource: Titlesource
  updatedAt: Updatedat1
  version: Version9
}
export interface TitleUpdatedEvent {
  conversationId: Conversationid9
  title: Title1
  titleSource: Titlesource1
  type: Type10
  version: Version11
}
export interface ResumeAcceptedEvent {
  generationId: Generationid8
  lastReceivedSeq: Lastreceivedseq
  type: Type11
  version: Version12
}
export interface ResumeSnapshotEvent {
  content: Content6
  conversationId: Conversationid10
  generationId: Generationid9
  lastSequence: Lastsequence
  messageId: Messageid7
  status: Status1
  type: Type12
  version: Version13
}
export interface ErrorEvent {
  code: Code1
  message: Message1
  requestId: Requestid
  type: Type13
  version: Version14
}
export interface HeartbeatEvent {
  type: Type14
  version: Version15
}
export interface PongEvent {
  type: Type15
  version: Version16
}
