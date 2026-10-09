export interface Conversation {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  archivedAt: string | null
  activeLeafMessageId: string | null
}

export interface ConversationSnapshot {
  version: 1
  conversations: Record<string, Conversation>
  activeConversationId: string | null
}

export interface ConversationGroup {
  label: string
  conversations: Conversation[]
}

export const CONVERSATIONS_STORAGE_KEY = 'noris-ai:conversations:v1'

export function normalizeTitle(title: string): string {
  return title.trim().replace(/\s+/g, ' ').slice(0, 120) || 'Neuer Chat'
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isDate(value: unknown): value is string {
  return typeof value === 'string' && Number.isFinite(Date.parse(value))
}

function isConversation(value: unknown): value is Conversation {
  if (!isRecord(value)) return false
  return typeof value.id === 'string' && value.id.length > 0
    && typeof value.title === 'string' && value.title.length <= 120
    && isDate(value.createdAt) && isDate(value.updatedAt)
    && (value.archivedAt === null || isDate(value.archivedAt))
    && (value.activeLeafMessageId === null || typeof value.activeLeafMessageId === 'string')
}

export function parseConversationSnapshot(raw: string): ConversationSnapshot | null {
  try {
    if (raw.length > 2_000_000) return null
    const value: unknown = JSON.parse(raw)
    if (!isRecord(value) || value.version !== 1 || !isRecord(value.conversations)) return null
    const conversations: Record<string, Conversation> = {}
    for (const [id, item] of Object.entries(value.conversations)) {
      if (!isConversation(item) || item.id !== id) return null
      Object.defineProperty(conversations, id, { value: item, enumerable: true, writable: true, configurable: true })
    }
    if (value.activeConversationId !== null && typeof value.activeConversationId !== 'string') return null
    const active = value.activeConversationId
    if (active !== null && (!Object.hasOwn(conversations, active) || conversations[active]?.archivedAt !== null)) return null
    return { version: 1, conversations, activeConversationId: active }
  }
  catch { return null }
}

export function groupConversations(conversations: readonly Conversation[], now = new Date()): ConversationGroup[] {
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1).getTime()
  const week = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 7).getTime()
  const groups: ConversationGroup[] = [
    { label: 'Heute', conversations: [] }, { label: 'Gestern', conversations: [] },
    { label: 'Letzte 7 Tage', conversations: [] }, { label: 'Älter', conversations: [] },
  ]
  for (const conversation of [...conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))) {
    const time = Date.parse(conversation.updatedAt)
    const index = time >= start ? 0 : time >= yesterday ? 1 : time >= week ? 2 : 3
    groups[index]?.conversations.push(conversation)
  }
  return groups.filter(group => group.conversations.length > 0)
}
