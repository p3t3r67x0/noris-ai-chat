import { describe, expect, it, vi, afterEach } from 'vitest'
import { ref } from 'vue'
import { createChatState } from '../../app/composables/useChat'
import { useChatDrafts } from '../../app/composables/useChatDrafts'
import { createMockTransport } from '../../app/lib/chat/mockTransport'
import { parseChatSnapshot } from '../../app/lib/chat/persistence'
import { visiblePath } from '../../app/lib/chat/types'
import type { ChatRequest, ChatTransport } from '../../app/lib/chat/types'

function fixture() {
  const requests: ChatRequest[] = []
  const transport: ChatTransport = { async *stream(request) {
    requests.push(structuredClone(request))
    yield { seq: 1, type: 'response.started' }
    yield { seq: 2, type: 'response.output_text.delta', delta: `Antwort ${request.attempt}` }
    yield { seq: 3, type: 'response.completed' }
  } }
  let id = 0
  const chat = createChatState(transport, { id: () => `id-${++id}`, now: () => '2026-10-09T12:00:00Z' })
  const settle = async () => { while (chat.stream.busy.value) await Promise.resolve() }
  return { chat, requests, settle }
}
afterEach(() => vi.useRealTimers())

describe('immutable conversation branches', () => {
  it('edits an earlier question into a sibling and restores the entire original continuation', async () => {
    const { chat, requests, settle } = fixture()
    chat.send('Original', 'balanced'); await settle()
    const original = chat.visible.value[0]!
    chat.send('Fortsetzung', 'balanced'); await settle()
    const originalPath = chat.visible.value.map(message => message.id)
    const originalContents = chat.visible.value.map(message => message.content)
    expect(chat.edit(original.id, 'Neue Frage', 'reasoning')).toBe(true)
    await settle()
    const edited = chat.visible.value[0]!
    expect(edited.editedFromMessageId).toBe(original.id)
    expect(requests.at(-1)?.messages).toEqual([{ role: 'user', content: 'Neue Frage' }])
    expect(chat.messages.value[original.id]?.content).toBe('Original')
    expect(chat.variants(edited.id).map(message => message.id)).toEqual([original.id, edited.id])
    expect(chat.selectVariant(original.id)).toBe(true)
    expect(chat.visible.value.map(message => message.id)).toEqual(originalPath)
    expect(chat.visible.value.map(message => message.content)).toEqual(originalContents)
    chat.selectVariant(edited.id)
    expect(chat.visible.value).toHaveLength(2)
  })
  it('regenerates a sibling, excludes its old answer from transport history and preserves both paths', async () => {
    const { chat, requests, settle } = fixture()
    chat.send('Frage', 'balanced'); await settle()
    const oldReply = chat.visible.value[1]!
    chat.send('Nachfrage', 'balanced'); await settle()
    const continuation = chat.visible.value.at(-1)!.id
    expect(chat.regenerate(oldReply.id, 'fast')).toBe(true); await settle()
    const nextReply = chat.visible.value[1]!
    expect(nextReply.id).not.toBe(oldReply.id)
    expect(nextReply.content).toBe('Antwort 2')
    expect(requests.at(-1)?.messages).toEqual([{ role: 'user', content: 'Frage' }])
    chat.selectVariant(oldReply.id)
    expect(chat.visible.value.at(-1)?.id).toBe(continuation)
    chat.selectVariant(nextReply.id)
    expect(chat.visible.value).toHaveLength(2)
    expect(Object.keys(chat.messages.value)).toHaveLength(5)
  })
  it('rejects branch actions during generation and across conversations', async () => {
    vi.useFakeTimers()
    const chat = createChatState(createMockTransport())
    chat.send('Frage', 'balanced')
    const user = chat.visible.value[0]!.id
    const answer = chat.visible.value[1]!.id
    expect(chat.edit(user, 'Neu', 'fast')).toBe(false)
    expect(chat.regenerate(answer, 'fast')).toBe(false)
    expect(chat.selectVariant(user)).toBe(false)
    await vi.runAllTimersAsync()
    chat.newChat()
    expect(chat.edit(user, 'Neu', 'fast')).toBe(false)
    expect(chat.regenerate(answer, 'fast')).toBe(false)
    expect(chat.selectVariant(user)).toBe(false)
  })
  it('clears only the submitted draft and deletes all data belonging to a removed chat', async () => {
    const { chat, settle } = fixture()
    chat.drafts.draft.value = 'Erster Entwurf'
    chat.send('Erster Entwurf', 'balanced'); await settle()
    const firstId = chat.conversations.activeId.value!
    chat.drafts.draft.value = 'Später weiter'
    chat.newChat()
    chat.drafts.draft.value = 'Zweiter Entwurf'
    chat.conversations.select(firstId)
    expect(chat.drafts.draft.value).toBe('Später weiter')
    chat.remove(firstId)
    expect(Object.values(chat.messages.value)).toHaveLength(0)
    expect(chat.drafts.records.value[firstId]).toBeUndefined()
    expect(Object.values(chat.drafts.records.value)).toContain('Zweiter Entwurf')
  })
})

describe('drafts and validated local persistence', () => {
  it('isolates drafts including the new-chat draft and safely handles prototype-like IDs', () => {
    const active = ref<string | null>(null)
    const drafts = useChatDrafts(active)
    drafts.draft.value = 'Noch kein Chat'
    active.value = '__proto__'; drafts.draft.value = 'Eigener Text'
    active.value = 'other'; expect(drafts.draft.value).toBe('')
    active.value = '__proto__'; expect(drafts.draft.value).toBe('Eigener Text')
    active.value = null; expect(drafts.draft.value).toBe('Noch kein Chat')
  })
  it('round trips messages, selected branches and drafts', async () => {
    const { chat, settle } = fixture()
    chat.send('Original', 'balanced'); await settle()
    const original = chat.visible.value[0]!.id
    chat.edit(original, 'Variante', 'balanced'); await settle()
    chat.selectVariant(original)
    chat.drafts.draft.value = 'Unfertig\nweiter'
    const parsed = parseChatSnapshot(JSON.stringify(chat.snapshot()))
    expect(parsed).not.toBeNull()
    const restored = fixture().chat
    restored.hydrate(parsed!)
    expect(restored.visible.value.map(message => message.content)).toEqual(['Original', 'Antwort 1'])
    expect(restored.drafts.draft.value).toBe('Unfertig\nweiter')
    const variant = restored.variants(original)[1]!
    restored.selectVariant(variant.id)
    expect(restored.visible.value[0]?.content).toBe('Variante')
  })
  it('marks interrupted generations cancelled when reloading', async () => {
    const { chat, settle } = fixture()
    chat.send('Frage', 'balanced'); await settle()
    chat.visible.value[1]!.status = 'streaming'
    const parsed = parseChatSnapshot(JSON.stringify(chat.snapshot()))!
    expect(Object.values(parsed.messages).find(message => message.role === 'assistant')?.status).toBe('cancelled')
    expect(chat.visible.value[1]?.status).toBe('streaming')
  })
  it.each(['parent', 'cycle', 'leaf', 'edit', 'oversize', 'role', 'draft'])('rejects corrupt %s data without partial hydration', async (kind) => {
    const { chat, settle } = fixture()
    chat.send('Frage', 'balanced'); await settle()
    const snapshot = JSON.parse(JSON.stringify(chat.snapshot())) as ReturnType<typeof chat.snapshot>
    const user = Object.values(snapshot.messages).find(message => message.role === 'user')!
    const assistant = Object.values(snapshot.messages).find(message => message.role === 'assistant')!
    if (kind === 'parent') assistant.parentMessageId = 'missing'
    if (kind === 'cycle') user.parentMessageId = assistant.id
    if (kind === 'leaf') snapshot.conversations.conversations[user.conversationId]!.activeLeafMessageId = 'missing'
    if (kind === 'edit') user.editedFromMessageId = assistant.id
    if (kind === 'oversize') assistant.content = 'x'.repeat(32_001)
    if (kind === 'role') assistant.role = 'user'
    if (kind === 'draft') snapshot.drafts.missing = 'Lost draft'
    expect(parseChatSnapshot(JSON.stringify(snapshot))).toBeNull()
  })
  it('rejects cross-conversation parents and never traverses prototype properties', async () => {
    const { chat, settle } = fixture()
    chat.send('Erste', 'balanced'); await settle()
    const oldAnswer = chat.visible.value[1]!.id
    chat.newChat(); chat.send('Zweite', 'balanced'); await settle()
    chat.visible.value[0]!.parentMessageId = oldAnswer
    expect(parseChatSnapshot(JSON.stringify(chat.snapshot()))).toBeNull()
    expect(() => visiblePath({}, 'c', '__proto__')).toThrow('Ungültiger Gesprächspfad')
    expect(parseChatSnapshot('invalid')).toBeNull()
  })
})
