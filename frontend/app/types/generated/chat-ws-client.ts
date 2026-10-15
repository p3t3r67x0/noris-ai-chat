/* Generated WebSocket v1 contract. Run pnpm api:generate. */
export type ChatWsCommand = (GenerateIncomingMessage | CancelIncomingMessage | ResumeIncomingMessage | PingIncomingMessage)
export type Assistantmessageid = string
/**
 * @maxItems 10
 */
export type Attachmentids = string[]
export type Attempt = number
export type Content = string
export type Conversationid = string
export type Conversationversion = number
export type Editedfrommessageid = (string | null)
export type Inputmessageid = string
export type Modelid = string
export type Operation = ("generate" | "continue")
export type Parentmessageid = (string | null)
export type Requestid = string
export type Language = ("de" | "en")
export type Mode = "web"
export type Version = 1
export type Researcheventversion = (1 | null)
export type Sourceassistantmessageid = (string | null)
export type Tooleventversion = (1 | null)
export type Type = "chat.generate"
export type Version1 = 1
export type Generationid = string
export type Type1 = "chat.cancel"
export type Version2 = 1
export type Generationid1 = string
export type Lastreceivedseq = number
export type Researcheventversion1 = (1 | null)
export type Tooleventversion1 = (1 | null)
export type Tooleventsonly = boolean
export type Type2 = "chat.resume"
export type Version3 = 1
export type Type3 = "chat.ping"
export type Version4 = 1

export interface GenerateIncomingMessage {
  assistantMessageId: Assistantmessageid
  attachmentIds?: Attachmentids
  attempt?: Attempt
  content: Content
  conversationId: Conversationid
  conversationVersion: Conversationversion
  editedFromMessageId?: Editedfrommessageid
  inputMessageId: Inputmessageid
  modelId: Modelid
  operation?: Operation
  parentMessageId?: Parentmessageid
  requestId: Requestid
  research?: (ResearchIntent | null)
  researchEventVersion?: Researcheventversion
  sourceAssistantMessageId?: Sourceassistantmessageid
  toolEventVersion?: Tooleventversion
  type: Type
  version: Version1
}
/**
 * Public intent, never an execution permission or a tool plan.
 */
export interface ResearchIntent {
  language: Language
  mode: Mode
  version: Version
}
export interface CancelIncomingMessage {
  generationId: Generationid
  type: Type1
  version: Version2
}
export interface ResumeIncomingMessage {
  generationId: Generationid1
  lastReceivedSeq?: Lastreceivedseq
  researchEventVersion?: Researcheventversion1
  toolEventVersion?: Tooleventversion1
  toolEventsOnly?: Tooleventsonly
  type: Type2
  version: Version3
}
export interface PingIncomingMessage {
  type: Type3
  version: Version4
}
