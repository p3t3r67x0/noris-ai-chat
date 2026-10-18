import { describe, expect, it } from 'vitest'
import { localConversationSearch, parseSearchQuery } from '../../app/lib/chat/search'
import { foldSearchText } from '../../app/lib/chat/searchCasefold'
import type { Conversation } from '../../app/lib/chat/conversations'
import type { ChatMessage } from '../../app/lib/chat/types'

const row = (id: string, title: string, day = 1): Conversation => ({ id, title, titleSource: 'manual', titleGenerationAttempted: true, createdAt: '2026-01-01T00:00:00Z', updatedAt: `2026-01-${String(day).padStart(2, '0')}T00:00:00Z`, archivedAt: null, activeLeafMessageId: null })
const message = (id: string, conversationId: string, content: string): ChatMessage => ({ id, conversationId, content, parentMessageId: null, role: 'user', status: 'completed', createdAt: '2026-01-01T00:00:00Z' })

describe('shared literal Unicode search semantics', () => {
  it.each([
    ['Straße STRASSE', 'strasse strasse', ['strasse']],
    ['Äpfel A\u0308PFEL', 'äpfel äpfel', ['äpfel']],
    ['Σ ς σ', 'σ σ σ', ['σ']],
    ['\u{10d50}', '\u{10d70}', ['\u{10d70}']],
    ['東京\u3000健康', '東京 健康', ['東京', '健康']],
    ['v0.12.3 %_ \\', 'v0.12.3 %_ \\', ['v0.12.3', '%_', '\\']],
    ['\u0085\u00a0\u2003', '', []],
  ])('normalizes %s consistently with the server', (value, phrase, terms) => {
    expect(parseSearchQuery(value as string)).toEqual({ phrase, terms, valid: true })
  })
  it('keeps accents and dotted i distinct and composes Hangul', () => {
    expect(foldSearchText('é')).not.toBe(foldSearchText('e'))
    expect(foldSearchText('İ')).not.toBe(foldSearchText('i'))
    expect(foldSearchText('\u1100\u1161')).toBe('가')
    expect(parseSearchQuery('x'.repeat(201)).valid).toBe(false)
    expect(parseSearchQuery(Array.from({ length: 33 }, (_, i) => i).join(' ')).valid).toBe(false)
    expect(parseSearchQuery('\0').valid).toBe(false)
  })
  it('ANDs across title and messages, keeps phrase rank and applies independent filters', () => {
    const rows = [row('split', 'Docker setup', 9), row('phrase', 'docker healthcheck', 1), { ...row('archived', 'Docker', 2), archivedAt: '2026-02-01T00:00:00Z', pinnedAt: '2026-01-01T00:00:00Z' }]
    const messages = [message('target', 'split', 'healthcheck'), message('archived-target', 'archived', 'healthcheck')]
    const find = (archive: 'active' | 'archived' | 'all', pin: 'all' | 'pinned' | 'unpinned') => localConversationSearch(rows, messages, 'Docker healthcheck', { archive, pin })
    expect(find('active', 'all').conversations.map(row => row.id)).toEqual(['phrase', 'split'])
    expect(find('all', 'pinned').conversations.map(row => row.id)).toEqual(['archived'])
    expect(find('archived', 'unpinned').conversations).toEqual([])
    expect(find('active', 'all').matches).toEqual([{ conversationId: 'split', messageId: 'target', excerpt: 'healthcheck' }])
  })
})
