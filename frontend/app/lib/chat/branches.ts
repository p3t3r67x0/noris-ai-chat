import { visiblePath } from './types'
import type { ChatMessage, MessageRecords } from './types'

export function siblingVariants(records: MessageRecords, messageId: string): ChatMessage[] {
  const selected = Object.hasOwn(records, messageId) ? records[messageId] : undefined
  if (!selected) return []
  return Object.values(records).filter(message => message.conversationId === selected.conversationId && message.parentMessageId === selected.parentMessageId && message.role === selected.role)
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt))
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
      .sort((a, b) => a.createdAt.localeCompare(b.createdAt)).at(-1)
    if (!child) return leaf
    leaf = child.id
  }
  throw new Error('Zyklus im Nachrichtenbaum')
}
