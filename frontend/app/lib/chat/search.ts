import type { Conversation } from './conversations'
import { compareConversations } from './conversations'
import type { ChatMessage } from './types'
import { foldSearchText } from './searchCasefold'
import { searchTextParts } from './searchHighlight'

export interface ConversationSearchFilters {
  archive: 'active' | 'archived' | 'all'
  pin: 'all' | 'pinned' | 'unpinned'
}

export function parseSearchQuery(value: string): { phrase: string, terms: string[], valid: boolean } {
  const phrase = foldSearchText(value).replace(/\p{White_Space}+/gu, ' ').replace(/^ +| +$/g, '')
  const terms = phrase ? [...new Set(phrase.split(' '))] : []
  return { phrase, terms, valid: Array.from(value).length <= 200 && terms.length <= 32 && !value.includes('\0') }
}

// The demo searches only locally available messages. The persistent mode always
// trusts the server result order, scope and snippets instead of re-filtering it.
export function localConversationSearch(conversations: readonly Conversation[], messages: readonly ChatMessage[], value: string, filters: ConversationSearchFilters) {
  const query = parseSearchQuery(value)
  const matches: { conversationId: string, messageId: string, excerpt: string }[] = []
  const ranks = new Map<string, boolean>()
  if (!query.valid) return { conversations: [], matches }
  const rows = conversations.filter(conversation => {
    if (filters.archive === 'active' && conversation.archivedAt) return false
    if (filters.archive === 'archived' && !conversation.archivedAt) return false
    if (filters.pin === 'pinned' && !conversation.pinnedAt) return false
    if (filters.pin === 'unpinned' && conversation.pinnedAt) return false
    const title = foldSearchText(conversation.title)
    const candidates = messages.filter(message => message.conversationId === conversation.id).map(message => ({ message, content: foldSearchText(message.content) }))
    if (!query.terms.every(term => title.includes(term) || candidates.some(row => row.content.includes(term)))) return false
    ranks.set(conversation.id, title.includes(query.phrase) || candidates.some(row => row.content.includes(query.phrase)))
    if (query.terms.length) {
      const score = (content: string) => content.includes(query.phrase) ? -1 : query.terms.findIndex(term => content.includes(term))
      const match = candidates.filter(row => query.terms.some(term => row.content.includes(term))).sort((a, b) => score(a.content) - score(b.content) || b.message.createdAt.localeCompare(a.message.createdAt) || b.message.id.localeCompare(a.message.id))[0]
      if (match) {
        // Presentation only: preserve original text and use the grapheme map to
        // locate expanded casefold matches without indexing the original string.
        const parts = searchTextParts(match.message.content, value)
        const index = parts.findIndex(part => part.matched)
        const offset = index < 0 ? 0 : parts.slice(0, index).reduce((sum, part) => sum + part.text.length, 0)
        const start = Math.max(0, offset - 60), end = Math.min(match.message.content.length, start + 200)
        matches.push({ conversationId: conversation.id, messageId: match.message.id, excerpt: `${start ? '…' : ''}${match.message.content.slice(start, end)}${end < match.message.content.length ? '…' : ''}` })
      }
    }
    return true
  })
  rows.sort(query.terms.length ? (a, b) => Number(ranks.get(b.id)) - Number(ranks.get(a.id)) || b.updatedAt.localeCompare(a.updatedAt) || b.id.localeCompare(a.id) : compareConversations)
  return { conversations: rows, matches }
}
