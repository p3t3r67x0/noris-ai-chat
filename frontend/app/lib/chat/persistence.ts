import { parseConversationSnapshot } from './conversations'
import type { ConversationSnapshot } from './conversations'
import { NEW_CHAT_DRAFT } from './types'
import { ABSOLUTE_MESSAGE_CHARS } from './limits'
import type { ChatMessage, MessageRecords } from './types'

export const CHAT_STORAGE_KEY = 'noris-ai:chat:v1'
export interface ChatSnapshot {
  version: 1
  conversations: ConversationSnapshot
  messages: MessageRecords
  drafts: Record<string, string>
  preferredLeaves: Record<string, string>
}
function record(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null && !Array.isArray(value) }
function validMessage(value: unknown): value is ChatMessage {
  if (!record(value)) return false
  return typeof value.id === 'string' && value.id.length > 0 && typeof value.conversationId === 'string'
    && (value.parentMessageId === null || typeof value.parentMessageId === 'string')
    && (value.role === 'user' || value.role === 'assistant')
    && typeof value.content === 'string' && value.content.length <= ABSOLUTE_MESSAGE_CHARS
    && typeof value.createdAt === 'string' && Number.isFinite(Date.parse(value.createdAt))
    && ['completed', 'cancelled', 'failed', 'submitting', 'streaming'].includes(String(value.status))
    && (value.role !== 'user' || value.status === 'completed')
    && (value.editedFromMessageId === undefined || typeof value.editedFromMessageId === 'string')
}
function own<T>(values: Record<string, T>, id: string): T | undefined { return Object.hasOwn(values, id) ? values[id] : undefined }
function insert<T>(values: Record<string, T>, key: string, value: T): void { Object.defineProperty(values, key, { value, enumerable: true, configurable: true, writable: true }) }

export function parseChatSnapshot(raw: string): ChatSnapshot | null {
  try {
    if (raw.length > 6_000_000) return null
    const data: unknown = JSON.parse(raw)
    if (!record(data) || data.version !== 1 || !record(data.messages) || !record(data.drafts) || !record(data.preferredLeaves)) return null
    const conversations = parseConversationSnapshot(JSON.stringify(data.conversations))
    if (!conversations || Object.keys(data.messages).length > 10_000) return null
    const messages: MessageRecords = {}
    for (const [id, value] of Object.entries(data.messages)) {
      if (!validMessage(value) || value.id !== id || !own(conversations.conversations, value.conversationId)) return null
      insert(messages, id, { ...value })
    }
    const checked = new Set<string>()
    for (const message of Object.values(messages)) {
      if (message.parentMessageId === null && message.role !== 'user') return null
      if (message.parentMessageId !== null) {
        const parent = own(messages, message.parentMessageId)
        if (!parent || parent.conversationId !== message.conversationId || parent.role === message.role) return null
      }
      if (message.editedFromMessageId !== undefined) {
        const original = own(messages, message.editedFromMessageId)
        if (!original || original.role !== 'user' || message.role !== 'user' || original.conversationId !== message.conversationId || original.parentMessageId !== message.parentMessageId) return null
      }
      const chain = new Set<string>()
      let current: ChatMessage | undefined = message
      while (current && !checked.has(current.id)) {
        if (chain.has(current.id)) return null
        chain.add(current.id)
        current = current.parentMessageId === null ? undefined : own(messages, current.parentMessageId)
      }
      for (const id of chain) checked.add(id)
    }
    for (const conversation of Object.values(conversations.conversations)) {
      if (conversation.activeLeafMessageId !== null && own(messages, conversation.activeLeafMessageId)?.conversationId !== conversation.id) return null
    }
    const drafts: Record<string, string> = {}
    for (const [id, text] of Object.entries(data.drafts)) {
      if ((id !== NEW_CHAT_DRAFT && !own(conversations.conversations, id)) || typeof text !== 'string' || text.length > ABSOLUTE_MESSAGE_CHARS * 2) return null
      insert(drafts, id, text)
    }
    const preferredLeaves: Record<string, string> = {}
    for (const [id, leaf] of Object.entries(data.preferredLeaves)) {
      if (typeof leaf !== 'string' || !own(messages, id) || own(messages, leaf)?.conversationId !== own(messages, id)?.conversationId) return null
      insert(preferredLeaves, id, leaf)
    }
    for (const message of Object.values(messages)) {
      if (message.status === 'submitting' || message.status === 'streaming') message.status = 'cancelled'
    }
    return { version: 1, conversations, messages, drafts, preferredLeaves }
  }
  catch { return null }
}
