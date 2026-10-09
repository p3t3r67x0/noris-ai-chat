import { describe, expect, it } from 'vitest'
import { createConversationState } from '../../app/composables/useConversations'
import { groupConversations, normalizeTitle, parseConversationSnapshot } from '../../app/lib/chat/conversations'
import { isChatModelId } from '../../app/composables/useModelSelection'

function state() {
  let sequence = 0
  return createConversationState({ id: () => `chat-${++sequence}`, now: () => '2026-10-09T12:00:00.000Z' })
}

describe('conversation management', () => {
  it('creates and selects an independent conversation', () => {
    const chats = state()
    const a = chats.create('Erste Frage')
    const b = chats.create('Zweite Frage')
    expect(chats.activeId.value).toBe(b.id)
    chats.select(a.id)
    expect(chats.active.value?.title).toBe('Erste Frage')
    expect(chats.visible.value).toHaveLength(2)
  })

  it('normalizes user titles and leaves chronology unchanged on rename', () => {
    const chats = state()
    const chat = chats.create()
    chats.rename(chat.id, '  Klarer\n Name  ')
    expect(chat.title).toBe('Klarer Name')
    expect(chat.createdAt).toBe(chat.updatedAt)
    expect(normalizeTitle(' ')).toBe('Neuer Chat')
    expect(normalizeTitle('a'.repeat(200))).toHaveLength(120)
  })

  it('archives and restores without removing a conversation', () => {
    const chats = state()
    const chat = chats.create('Aufbewahren')
    chats.archive(chat.id)
    expect(chats.visible.value).toHaveLength(0)
    expect(chats.archived.value).toHaveLength(1)
    expect(chats.activeId.value).toBeNull()
    chats.select(chat.id)
    expect(chats.activeId.value).toBeNull()
    chats.restore(chat.id)
    expect(chats.activeId.value).toBe(chat.id)
  })

  it('deletes only the requested conversation and clears a stale selection', () => {
    const chats = state()
    const keep = chats.create('Behalten')
    const remove = chats.create('Entfernen')
    chats.remove(remove.id)
    expect(chats.visible.value.map(item => item.id)).toEqual([keep.id])
    expect(chats.activeId.value).toBeNull()
    chats.select('missing')
    chats.rename('missing', 'ignored')
    chats.archive('missing')
    chats.rename('__proto__', 'ignored')
    chats.archive('constructor')
    expect(Object.prototype).not.toHaveProperty('title')
    expect(chats.visible.value).toHaveLength(1)
  })

  it('round-trips a selected conversation through validated local persistence', () => {
    const chats = state()
    const selected = chats.create('Persistiert')
    const saved = parseConversationSnapshot(JSON.stringify(chats.snapshot()))
    expect(saved).not.toBeNull()
    if (!saved) throw new Error('Snapshot was unexpectedly rejected')
    const restored = state()
    restored.hydrate(saved)
    expect(restored.activeId.value).toBe(selected.id)
    expect(restored.active.value?.title).toBe('Persistiert')
  })

  it.each(['not json', '{}', '{"version":2,"conversations":{}}', JSON.stringify({ version: 1, conversations: {}, activeConversationId: 'missing' })])('rejects malformed or incompatible saved state: %s', (raw) => {
    expect(parseConversationSnapshot(raw)).toBeNull()
  })

  it('rejects mismatched IDs and archived active selections', () => {
    const chats = state()
    const chat = chats.create()
    const snapshot = chats.snapshot()
    expect(parseConversationSnapshot(JSON.stringify({ ...snapshot, conversations: { wrong: chat } }))).toBeNull()
    chat.archivedAt = '2026-10-09T13:00:00.000Z'
    expect(parseConversationSnapshot(JSON.stringify(snapshot))).toBeNull()
  })

  it('groups local calendar days and orders by recent activity', () => {
    const chats = state()
    const today = chats.create('Heute')
    const yesterday = chats.create('Gestern')
    const week = chats.create('Woche')
    const old = chats.create('Älter')
    const now = new Date(2026, 9, 9, 12)
    today.updatedAt = new Date(2026, 9, 9, 10).toISOString()
    yesterday.updatedAt = new Date(2026, 9, 8, 23).toISOString()
    week.updatedAt = new Date(2026, 9, 3, 8).toISOString()
    old.updatedAt = new Date(2026, 8, 30, 8).toISOString()
    expect(groupConversations([old, week, yesterday, today], now).map(group => [group.label, group.conversations[0]?.title])).toEqual([
      ['Heute', 'Heute'], ['Gestern', 'Gestern'], ['Letzte 7 Tage', 'Woche'], ['Älter', 'Älter'],
    ])
  })

  it('accepts only configured model identifiers', () => {
    expect(isChatModelId('balanced')).toBe(true)
    expect(isChatModelId('unknown-provider')).toBe(false)
    expect(isChatModelId(null)).toBe(false)
  })
})
