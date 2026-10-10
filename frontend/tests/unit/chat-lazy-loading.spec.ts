import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { ChatBackend, messageFromServer } from '../../app/lib/chat/backend'
import { ChatLoadCache } from '../../app/lib/chat/loadCache'
import { createChatState } from '../../app/composables/useChat'
import { CHAT_CACHE_KEY, useChatBackend } from '../../app/composables/useChatBackend'
import type { ApiSchemas } from '../../app/types/generated/api'
import { visiblePath } from '../../app/lib/chat/types'

const id = (number: number) => `00000000-0000-4000-8000-${String(number).padStart(12, '0')}`
function conversation(number: number): ApiSchemas['ConversationResponse'] {
  return { id: id(number), title: `Chat ${number}`, titleSource: 'manual', version: 1, activeLeafMessageId: id(number + 1000), createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z', archivedAt: null, lastMessageAt: null }
}
function path(number: number): ApiSchemas['ActivePathResponse'] {
  const c = conversation(number)
  return { conversation: c, leafMessageId: c.activeLeafMessageId, nextCursor: null, hasMore: false, boundaryParentId: id(99999), variants: [], messages: [{ id: c.activeLeafMessageId!, conversationId: c.id, parentMessageId: id(99999), role: 'assistant', content: `Answer ${number}`, status: 'completed', generationId: null, modelId: 'fixture', editedFromMessageId: null, createdAt: c.createdAt, updatedAt: c.updatedAt }] }
}
const wrappers: Array<{ unmount: () => void }> = []
afterEach(() => { for (const wrapper of wrappers.splice(0)) wrapper.unmount(); localStorage.clear() })

function client(active = 99) {
  const calls: string[] = []
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost')
    calls.push(url.pathname + url.search)
    let data: unknown = {}
    if (url.pathname === '/api/v1/conversations') data = { conversations: Array.from({ length: 50 }, (_, i) => conversation(i + 1)), nextCursor: 'page-2', hasMore: true }
    else if (url.pathname === '/api/v1/chat/preferences') data = { activeConversationId: id(active), modelId: 'fixture' }
    else if (url.pathname === '/api/v1/chat/drafts') data = { drafts: [] }
    else if (url.pathname.endsWith('/active-path')) data = path(Number(url.pathname.split('/')[4]?.slice(-12)))
    else if (url.pathname.startsWith('/api/v1/conversations/')) data = conversation(Number(url.pathname.split('/')[4]?.slice(-12)))
    return new Response(JSON.stringify(data), { status: 200 })
  })
  return { backend: new ChatBackend(fetcher), calls, fetcher }
}

describe('lazy chat resources', () => {
  it('loads exactly one active window, including an active conversation outside page one', async () => {
    const { backend, calls } = client()
    const metadata = vi.fn(); backend.onMetadata = metadata
    const result = await backend.load()
    expect(calls.filter(url => url.includes('/active-path'))).toHaveLength(1)
    expect(calls.some(url => url.endsWith('/messages'))).toBe(false)
    expect(backend.initialPage?.conversations).toHaveLength(50)
    expect(result.path?.messages).toHaveLength(1)
    expect(result.activeConversationId).toBe(id(99))
    expect(calls).toContain(`/api/v1/conversations/${id(99)}`)
    expect(metadata).toHaveBeenCalledTimes(2)
    expect(metadata.mock.calls[0]?.[0]).toHaveLength(50)
    expect(calls.find(url => url.includes('/chat/drafts'))).toContain('keys=__new__')
    const message = result.path!.messages[0]!
    const records = { [message.id]: messageFromServer(message) }
    expect(() => visiblePath(records, id(99), message.id)).toThrow()
    expect(visiblePath(records, id(99), message.id, id(99999))).toHaveLength(1)
  })
  it('bounds loaded windows while keeping a running inactive generation', async () => {
    const { backend } = client(1)
    const transport = { backend, stream: async function* () {} }
    const state = createChatState(transport)
    let sync!: ReturnType<typeof useChatBackend>
    wrappers.push(mount(defineComponent({ setup() { sync = useChatBackend(state, transport); return () => h('div') } })))
    await vi.waitFor(() => expect(sync.backendReady.value).toBe(true))
    state.generatingConversationId.value = id(1)
    for (let number = 2; number <= 13; number++) {
      state.conversations.select(id(number)); await nextTick()
      await vi.waitFor(() => expect(state.visible.value[0]?.content).toBe(`Answer ${number}`))
    }
    expect(Object.keys(state.messages.value)).toHaveLength(10)
    expect(state.messages.value[id(1001)]?.content).toBe('Answer 1')
    expect(state.messages.value[id(1002)]).toBeUndefined()
    const read = vi.spyOn(backend, 'path')
    state.conversations.select(id(2)); await nextTick()
    await vi.waitFor(() => expect(state.visible.value[0]?.content).toBe('Answer 2'))
    expect(read).toHaveBeenCalledWith(id(2), {}, expect.any(AbortSignal))
  })
  it('caches repeated opens and ignores an aborted late response after switching conversations', async () => {
    const { backend } = client(1)
    const transport = { backend, stream: async function* () {} }
    const state = createChatState(transport)
    let sync!: ReturnType<typeof useChatBackend>
    const wrapper = mount(defineComponent({ setup() { sync = useChatBackend(state, transport); return () => h('div') } }))
    wrappers.push(wrapper)
    await vi.waitFor(() => expect(sync.backendReady.value).toBe(true))
    const original = backend.path.bind(backend)
    let resolveA!: (value: ApiSchemas['ActivePathResponse']) => void
    const read = vi.spyOn(backend, 'path').mockImplementation((key, options, signal) => key === id(2) ? new Promise(resolve => { resolveA = resolve }) : original(key, options, signal))
    state.conversations.select(id(2)); await nextTick()
    await vi.waitFor(() => expect(read).toHaveBeenCalledWith(id(2), {}, expect.any(AbortSignal)))
    state.conversations.select(id(3)); await nextTick()
    await vi.waitFor(() => expect(state.visible.value[0]?.content).toBe('Answer 3'))
    resolveA(path(2)); await nextTick(); await nextTick()
    expect(state.conversations.activeId.value).toBe(id(3))
    expect(state.visible.value[0]?.content).toBe('Answer 3')
    expect(state.messages.value[id(1002)]).toBeUndefined()
    state.conversations.select(id(1)); await nextTick()
    expect(read.mock.calls.filter(([key]) => key === id(1))).toHaveLength(0)
  })
  it('finishing an inactive generation does not abort the active conversation read', async () => {
    const { backend } = client(1)
    const transport = { backend, stream: async function* () {} }
    const state = createChatState(transport)
    let sync!: ReturnType<typeof useChatBackend>
    wrappers.push(mount(defineComponent({ setup() { sync = useChatBackend(state, transport); return () => h('div') } })))
    await vi.waitFor(() => expect(sync.backendReady.value).toBe(true))
    state.generatingConversationId.value = id(1); await nextTick()
    const resolvers = new Map<string, (value: ApiSchemas['ActivePathResponse']) => void>()
    const read = vi.spyOn(backend, 'path').mockImplementation(key => new Promise(resolve => { resolvers.set(key, resolve) }))
    state.conversations.select(id(2)); await nextTick()
    await vi.waitFor(() => expect(resolvers.has(id(2))).toBe(true))
    const signal = read.mock.calls.find(([key]) => key === id(2))![2]!
    state.generatingConversationId.value = null; await nextTick()
    await vi.waitFor(() => expect(resolvers.has(id(1))).toBe(true))
    resolvers.get(id(1))!(path(1)); await nextTick(); await nextTick()
    expect(signal.aborted).toBe(false)
    expect(sync.pagination.historyLoading.value).toBe(true)
    resolvers.get(id(2))!(path(2))
    await vi.waitFor(() => expect(state.visible.value[0]?.content).toBe('Answer 2'))
    expect(sync.pagination.historyLoading.value).toBe(false)
  })
  it('corrupt optional browser caches do not prevent database loading or socket connection', async () => {
    for (const key of [CHAT_CACHE_KEY, 'noris-ai:chat-scroll:v1', 'noris-ai:offline-drafts:v1']) localStorage.setItem(key, '{broken')
    const { backend } = client(1)
    const connect = vi.fn(async () => {})
    const transport = { backend, connect, stream: async function* () {} }
    const state = createChatState(transport)
    wrappers.push(mount(defineComponent({ setup() { useChatBackend(state, transport); return () => h('div') } })))
    await vi.waitFor(() => expect(connect).toHaveBeenCalledOnce())
    expect(state.visible.value[0]?.content).toBe('Answer 1')
  })
  it('moves an out-of-page active chat into the sidebar on a live title update without replacing messages', async () => {
    const { backend } = client(99)
    const transport = { backend, stream: async function* () {} }
    const state = createChatState(transport)
    let sync!: ReturnType<typeof useChatBackend>
    wrappers.push(mount(defineComponent({ setup() { sync = useChatBackend(state, transport); return () => h('div') } })))
    await vi.waitFor(() => expect(sync.backendReady.value).toBe(true))
    expect(sync.pagination.conversations.value.some(c => c.id === id(99))).toBe(false)
    const read = vi.spyOn(backend, 'path')
    backend.remember({ ...conversation(99), version: 2, title: 'Updated title', updatedAt: '2026-01-02T00:00:00Z' })
    expect(sync.pagination.conversations.value[0]?.title).toBe('Updated title')
    expect(state.visible.value[0]?.content).toBe('Answer 99')
    expect(read).not.toHaveBeenCalled()
  })
})

describe('bounded read cache', () => {
  it('evicts least recently used windows and protects active, running and unsynced chats', () => {
    const cache = new ChatLoadCache(3)
    for (const key of ['active', 'running', 'old', 'new']) cache.touch(key, 1)
    expect(cache.evictions(new Set(['active', 'running']))).toEqual(['old'])
    expect(cache.valid('active', 1)).toBe(true)
    cache.touch('next', 1)
    expect(cache.evictions(new Set(['active', 'running']))).toEqual(['new'])
  })
  it('deduplicates concurrent reads, retries errors, and expires changed or stale versions', async () => {
    let now = 0
    const cache = new ChatLoadCache(10, 30, () => now)
    const read = vi.fn(async () => 42)
    expect(await Promise.all([cache.read('chat', read), cache.read('chat', read)])).toEqual([42, 42])
    expect(read).toHaveBeenCalledOnce()
    const failure = vi.fn(async () => { throw new Error('offline') })
    await expect(cache.read('chat', failure)).rejects.toThrow('offline')
    expect(await cache.read('chat', read)).toBe(42)
    cache.touch('chat', 2)
    expect(cache.valid('chat', 1)).toBe(false)
    expect(cache.valid('chat', 2)).toBe(true)
    now = 31
    expect(cache.valid('chat', 2)).toBe(false)
  })
})
