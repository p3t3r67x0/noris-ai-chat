import { visiblePath } from './types'
import type { ChatMessage, MessageRecords } from './types'

/** Index only branch metadata; streamed content does not invalidate membership. */
export function indexSiblingVariants(records: MessageRecords): ReadonlyMap<string, readonly ChatMessage[]> {
  const groups = new Map<string, ChatMessage[]>()
  for (const message of Object.values(records)) {
    const key = JSON.stringify([message.conversationId, message.parentMessageId, message.role])
    const siblings = groups.get(key) ?? []
    siblings.push(message)
    groups.set(key, siblings)
  }
  const index = new Map<string, readonly ChatMessage[]>()
  for (const siblings of groups.values()) {
    siblings.sort((a, b) => Date.parse(a.createdAt) - Date.parse(b.createdAt))
    for (const message of siblings) index.set(message.id, siblings)
  }
  return index
}

export function siblingVariants(records: MessageRecords, messageId: string): ChatMessage[] {
  const selected = Object.hasOwn(records, messageId) ? records[messageId] : undefined
  if (!selected) return []
  return Object.values(records).filter(message => message.conversationId === selected.conversationId && message.parentMessageId === selected.parentMessageId && message.role === selected.role)
    .sort((a, b) => Date.parse(a.createdAt) - Date.parse(b.createdAt))
}

export function variantLeaf(records: MessageRecords, preferred: Record<string, string>, messageId: string): string {
  const message = Object.hasOwn(records, messageId) ? records[messageId] : undefined
  if (!message) throw new Error('Variante nicht gefunden')
  const saved = Object.hasOwn(preferred, messageId) ? preferred[messageId] : undefined
  if (saved && Object.hasOwn(records, saved) && visiblePath(records, message.conversationId, saved).some(node => node.id === messageId)) return saved
  let leaf = messageId
  const seen = new Set<string>()
  while (!seen.has(leaf)) {
    seen.add(leaf)
    const child = Object.values(records).filter(node => node.conversationId === message.conversationId && node.parentMessageId === leaf)
      .sort((a, b) => Date.parse(a.createdAt) - Date.parse(b.createdAt)).at(-1)
    if (!child) return leaf
    leaf = child.id
  }
  throw new Error('Zyklus im Nachrichtenbaum')
}
