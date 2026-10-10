import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { ChatBackend } from '../../app/lib/chat/backend'
import { CHAT_STORAGE_KEY } from '../../app/lib/chat/persistence'
import { createChatState } from '../../app/composables/useChat'
import { useChatBackend } from '../../app/composables/useChatBackend'

const id = '00000000-0000-4000-8000-000000000001'
const user = '00000000-0000-4000-8000-000000000002'
const reply = '00000000-0000-4000-8000-000000000003'
const time = '2026-10-10T00:00:00Z'
const raw = JSON.stringify({ version: 1, conversations: { version: 1, activeConversationId: id, conversations: { [id]: { id, title: 'Synthetischer Import', titleSource: 'manual', titleGenerationAttempted: true, createdAt: time, updatedAt: time, archivedAt: null, activeLeafMessageId: reply } } }, messages: {
  [user]: { id: user, conversationId: id, parentMessageId: null, role: 'user', content: 'Synthetische Frage', status: 'completed', createdAt: time },
  [reply]: { id: reply, conversationId: id, parentMessageId: user, role: 'assistant', content: 'Unvollständige Antwort', status: 'streaming', createdAt: time },
}, drafts: { [id]: 'Synthetischer Entwurf' }, preferredLeaves: { [user]: reply } })
const wrappers: ReturnType<typeof mount>[] = []
afterEach(() => { wrappers.splice(0).forEach(wrapper => wrapper.unmount()); localStorage.clear() })

async function client(snapshot = raw) {
  localStorage.setItem(CHAT_STORAGE_KEY, snapshot)
  const backend = new ChatBackend()
  const load = vi.spyOn(backend, 'load').mockResolvedValue({ metadata: [], activeConversationId: null, path: null, drafts: {} })
  const request = vi.spyOn(backend, 'request').mockResolvedValue({ imported: [id], skipped: [], conflicts: [] })
  const transport = { backend, stream: async function* () {} }
  const state = createChatState(transport)
  let sync!: ReturnType<typeof useChatBackend>
  wrappers.push(mount(defineComponent({ setup() { sync = useChatBackend(state, transport); return () => h('div') } })))
  await vi.waitFor(() => expect(sync.backendReady.value).toBe(true))
  return { sync, load, request }
}

describe('existing browser snapshot import', () => {
  it('does not import on mount and validates the snapshot on explicit import without changing its backup', async () => {
    const { sync, request, load } = await client()
    expect(sync.importAvailable.value).toBe(true)
    expect(request).not.toHaveBeenCalled()
    await sync.importLocalChats()
    expect(request).toHaveBeenCalledExactlyOnceWith('/conversations/import', 'POST', expect.objectContaining({
      drafts: { [id]: 'Synthetischer Entwurf' }, activeConversationId: id,
      messages: expect.arrayContaining([expect.objectContaining({ id: reply, status: 'cancelled' })]),
    }))
    expect(load).toHaveBeenCalledTimes(2)
    expect(sync.storageWarning.value).toContain('1 Chats importiert')
    expect(localStorage.getItem(CHAT_STORAGE_KEY)).toBe(raw)
  })

  it('rejects an invalid snapshot before any request and retains the original bytes', async () => {
    const { sync, request } = await client('{invalid')
    await sync.importLocalChats()
    expect(request).not.toHaveBeenCalled()
    expect(sync.storageWarning.value).toContain('ungültig')
    expect(localStorage.getItem(CHAT_STORAGE_KEY)).toBe('{invalid')
  })

  it('blocks concurrent imports and reports already imported conversations', async () => {
    const { sync, request } = await client()
    let finish!: (result: unknown) => void
    request.mockImplementation(() => new Promise(resolve => { finish = resolve }))
    const first = sync.importLocalChats()
    await sync.importLocalChats()
    expect(request).toHaveBeenCalledOnce()
    finish({ imported: [], skipped: [id], conflicts: [] }); await first
    expect(sync.storageWarning.value).toContain('0 Chats importiert, 1 bereits vorhanden')
    expect(sync.importBusy.value).toBe(false)
    expect(localStorage.getItem(CHAT_STORAGE_KEY)).toBe(raw)
  })

  it.each(['conflict', 'network'])('reports %s errors and keeps the snapshot for retry', async (failure) => {
    const { sync, request, load } = await client()
    if (failure === 'conflict') request.mockResolvedValueOnce({ imported: [], skipped: [], conflicts: [{ conversationId: id }] })
    else request.mockRejectedValueOnce(new Error('Synthetischer Verbindungsfehler'))
    await sync.importLocalChats()
    expect(sync.storageWarning.value).toContain(failure === 'conflict' ? 'Konflikte' : 'Verbindungsfehler')
    expect(load).toHaveBeenCalledOnce()
    expect(sync.importBusy.value).toBe(false)
    expect(localStorage.getItem(CHAT_STORAGE_KEY)).toBe(raw)
    await sync.importLocalChats()
    expect(sync.storageWarning.value).toContain('1 Chats importiert')
  })
})
