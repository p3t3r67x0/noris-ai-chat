import { afterEach, describe, expect, it, vi } from 'vitest'
import { createChatState } from '../../app/composables/useChat'
import { createMockTransport } from '../../app/lib/chat/mockTransport'
import { parseChatSnapshot } from '../../app/lib/chat/persistence'

afterEach(() => { vi.useRealTimers() })
describe('local conversation visibility and recovery', () => {
  it('keeps a new conversation and saved draft hidden after rename, archive and reload', () => {
    const chat = createChatState(createMockTransport())
    const empty = chat.conversations.create()
    chat.drafts.draft.value = 'Saved draft'
    chat.conversations.rename(empty.id, 'Manual draft title')
    expect(chat.conversations.visible.value).toEqual([])
    const saved = parseChatSnapshot(JSON.stringify(chat.snapshot()))!
    expect(saved.drafts[empty.id]).toBe('Saved draft')
    const reloaded = createChatState(createMockTransport())
    reloaded.hydrate(saved)
    expect(reloaded.conversations.visible.value).toEqual([])
    expect(reloaded.drafts.draft.value).toBe('Saved draft')
    reloaded.conversations.archive(empty.id)
    expect(reloaded.conversations.archived.value).toEqual([])
    expect(reloaded.conversations.records.value[empty.id]?.title).toBe('Manual draft title')
  })

  it('recovers historical empty rows without deleting drafts and reveals stored input before generation finishes', async () => {
    vi.useFakeTimers()
    const chat = createChatState(createMockTransport({ initialDelay: 100, chunkDelay: 100 }))
    const empty = chat.conversations.create('Named legacy draft')
    const legacy = chat.snapshot()
    legacy.conversations.conversations[empty.id]!.sidebarVisible = true
    legacy.drafts[empty.id] = 'Unsent legacy draft'
    const recovered = parseChatSnapshot(JSON.stringify(legacy))!
    chat.hydrate(recovered)
    expect(chat.conversations.visible.value).toEqual([])
    expect(chat.drafts.draft.value).toBe('Unsent legacy draft')
    chat.send('Wie steht es damit?', 'balanced')
    expect(chat.conversations.visible.value.map(row => row.id)).toEqual([empty.id])
    await vi.runAllTimersAsync()
    const saved = parseChatSnapshot(JSON.stringify(chat.snapshot()))!
    const reloaded = createChatState(createMockTransport())
    reloaded.hydrate(saved)
    expect(reloaded.conversations.visible.value.map(row => row.id)).toEqual([empty.id])
  })
})
