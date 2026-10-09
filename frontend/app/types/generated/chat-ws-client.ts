/* Generated WebSocket v1 contract. Run pnpm api:generate. */
export type ChatWsCommand = (GenerateIncomingMessage | CancelIncomingMessage | ResumeIncomingMessage | PingIncomingMessage)
export type Assistantmessageid = string
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
export type Sourceassistantmessageid = (string | null)
export type Type = "chat.generate"
export type Version = 1
export type Generationid = string
export type Type1 = "chat.cancel"
export type Version1 = 1
export type Generationid1 = string
export type Lastreceivedseq = number
export type Type2 = "chat.resume"
export type Version2 = 1
export type Type3 = "chat.ping"
export type Version3 = 1

export interface GenerateIncomingMessage {
  assistantMessageId: Assistantmessageid
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
  sourceAssistantMessageId?: Sourceassistantmessageid
  type: Type
  version: Version
}
export interface CancelIncomingMessage {
  generationId: Generationid
  type: Type1
  version: Version1
}
export interface ResumeIncomingMessage {
  generationId: Generationid1
  lastReceivedSeq?: Lastreceivedseq
  type: Type2
  version: Version2
}
export interface PingIncomingMessage {
  type: Type3
  version: Version3
}
