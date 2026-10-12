import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import ConversationTitle from '../../app/components/chat/ConversationTitle.vue'
import { createChatState } from '../../app/composables/useChat'
import { useChatBackend } from '../../app/composables/useChatBackend'
import { ChatBackend } from '../../app/lib/chat/backend'
import { createWebSocketTransport } from '../../app/lib/chat/webSocketTransport'
import type { ApiSchemas } from '../../app/types/generated/api'

const initial: ApiSchemas['ConversationResponse'] = {
  id: 'fe85558b-9db3-42a5-9217-7b1d4b451ccf', title: 'Neuer Chat', titleSource: 'fallback', version: 2,
  createdAt: '2026-10-12T12:00:00Z', updatedAt: '2026-10-12T12:00:00Z', archivedAt: null, activeLeafMessageId: null, lastMessageAt: null,
}
const generated = { ...initial, title: 'Automatische Chat-Zusammenfassungen', titleSource: 'generated' as const, version: 3 }
const manual = { ...generated, title: 'Meine eigenen Zusammenfassungen', titleSource: 'manual' as const, version: 4 }

class Socket extends EventTarget {
  static OPEN = 1
  static instances: Socket[] = []
  readyState = 0
  constructor() {
    super(); Socket.instances.push(this)
    setTimeout(() => { this.readyState = 1; this.dispatchEvent(new Event('open')) }, 0)
  }
  send(): void {}
  close(): void { this.readyState = 3; this.dispatchEvent(new Event('close')) }
  event(value: unknown): void { this.dispatchEvent(new MessageEvent('message', { data: JSON.stringify(value) })) }
}
const wrappers: ReturnType<typeof mount>[] = []
afterEach(() => {
  wrappers.splice(0).forEach(wrapper => wrapper.unmount())
  vi.unstubAllGlobals(); localStorage.clear()
})

async function fixture() {
  Socket.instances = []
  let authority = initial
  let pendingRead: Promise<ApiSchemas['ConversationResponse']> | undefined
  const fetcher = vi.fn<typeof fetch>(async (input) => {
    const path = String(input)
    if (path.includes('/chat/ws-ticket')) return Response.json({ ticketId: 'synthetic-ticket' })
    if (path.includes('/chat/preferences')) return Response.json({ activeConversationId: null, modelId: null })
    if (path.includes('/chat/drafts')) return Response.json({ drafts: [] })
    if (path === `/api/v1/conversations/${initial.id}`) return Response.json(await (pendingRead ?? Promise.resolve(authority)))
    if (path.includes('/conversations?')) return Response.json({ conversations: [authority], nextCursor: null, hasMore: false })
    throw new Error(`Unexpected fixture request: ${path}`)
  })
  const backend = new ChatBackend(fetcher)
  const transport = createWebSocketTransport({ backend, url: 'ws://localhost/chat', socket: Socket as unknown as typeof WebSocket })
  const state = createChatState(transport)
  let sync!: ReturnType<typeof useChatBackend>
  const wrapper = mount(defineComponent({
    setup() {
      sync = useChatBackend(state, transport)
      return () => h('nav', sync.pagination.conversations.value.map(c => h('button', { title: c.title }, [
        h(ConversationTitle, { title: c.title, source: c.titleSource, onFit: (expected: string, title: string) => state.conversations.fitTitle(c.id, expected, title) }),
      ])))
    },
  }))
  wrappers.push(wrapper)
  await vi.waitFor(() => expect(sync.backendReady.value).toBe(true))
  await transport.connect?.()
  return { state, backend, wrapper, sync, fetcher, socket: Socket.instances.at(-1)!, authority: (value: typeof initial) => { authority = value }, delayRead: (value: Promise<typeof initial>) => { pendingRead = value } }
}

describe('authoritative sidebar title synchronization', () => {
  it.each(['chat.title.updated', 'chat.conversation.updated'])('renders %s without replacing a wide generated title with a fallback', async (type) => {
    // Reproduce the available sidebar width: the generated title is wider than
    // the label, while "Neuer Chat" fits. Layout must never rewrite metadata.
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(180)
    vi.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue([new DOMRect()] as unknown as DOMRectList)
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) { return new DOMRect(0, 0, (this.textContent?.length ?? 0) * 9, 20) })
    const { state, wrapper, backend, socket, authority } = await fixture()
    authority(generated)
    socket.event(type === 'chat.title.updated'
      ? { version: 1, type, conversationId: initial.id, title: generated.title, titleSource: 'generated' }
      : { version: 1, type, conversation: generated })

    await vi.waitFor(() => expect(wrapper.get('button').attributes('title')).toBe(generated.title))
    expect(wrapper.get('[data-title-source]').attributes('data-title-source')).toBe('generated')
    expect(state.conversations.records.value[initial.id]).toMatchObject(generated)
    expect(backend.versions.get(initial.id)).toBe(3)
    expect(wrapper.findComponent(ConversationTitle).emitted('fit')).toBeUndefined()
  })

  it('rejects stale title reads and conversation events after a newer manual rename', async () => {
    const { state, wrapper, backend, socket, delayRead } = await fixture()
    let release!: (value: typeof initial) => void
    delayRead(new Promise(resolve => { release = resolve }))
    socket.event({ version: 1, type: 'chat.title.updated', conversationId: initial.id, title: generated.title, titleSource: 'generated' })
    socket.event({ version: 1, type: 'chat.conversation.updated', conversation: manual })
    release(generated)
    socket.event({ version: 1, type: 'chat.conversation.updated', conversation: initial })

    await vi.waitFor(() => expect(wrapper.get('button').attributes('title')).toBe(manual.title))
    expect(state.conversations.records.value[initial.id]).toMatchObject(manual)
    expect(backend.versions.get(initial.id)).toBe(4)
  })

  it('keeps an old pin outside regular pagination, and moves it once on a versioned unpin', async () => {
    const { state, backend, sync, socket } = await fixture()
    const old = { ...manual, id: '00000000-0000-4000-8000-000000000999', updatedAt: '2020-01-01T00:00:00Z', pinnedAt: '2026-10-12T12:00:00Z', version: 5 }
    socket.event({ version: 1, type: 'chat.conversation.updated', conversation: old })
    await vi.waitFor(() => expect(sync.pagination.conversations.value.filter(c => c.id === old.id)).toHaveLength(1))
    const unpinned = { ...old, pinnedAt: null, version: 6 }
    backend.remember(unpinned)
    backend.remember(old)
    expect(state.conversations.records.value[old.id]?.pinnedAt).toBeNull()
    expect(sync.pagination.conversations.value.filter(c => c.id === old.id)).toHaveLength(1)
    expect(state.conversations.activeId.value).toBeNull()
    backend.forget(old.id, 7)
    backend.remember(unpinned)
    expect(sync.pagination.conversations.value.some(c => c.id === old.id)).toBe(false)
  })

  it('persists direct pin and unpin through the existing versioned resource client', async () => {
    const { state, backend, sync } = await fixture()
    vi.spyOn(backend, 'patch').mockImplementation(async (id, change) => {
      backend.remember({ ...manual, id, pinnedAt: change.pinned ? '2026-10-12T12:00:00Z' : null, version: (backend.versions.get(id) ?? 0) + 1 })
    })
    await state.conversations.setPinned(initial.id, true)
    expect(sync.pagination.conversations.value[0]?.pinnedAt).toBeTruthy()
    await state.conversations.setPinned(initial.id, false)
    expect(sync.pagination.conversations.value[0]?.pinnedAt).toBeNull()
    expect(backend.patch).toHaveBeenNthCalledWith(1, initial.id, { pinned: true })
    expect(backend.patch).toHaveBeenNthCalledWith(2, initial.id, { pinned: false })
  })

  it('ignores a stale pinned-page response after a newer unpin event', async () => {
    const { state, backend, sync } = await fixture()
    const pinned = { ...manual, pinnedAt: '2026-10-12T12:00:00Z', version: 5 }
    backend.remember(pinned)
    let release!: (value: ApiSchemas['ConversationListResponse']) => void
    vi.spyOn(backend, 'page').mockReturnValue(new Promise(resolve => { release = resolve }))
    const loading = sync.pagination.reloadPinned()
    backend.remember({ ...pinned, pinnedAt: null, version: 6 })
    release({ conversations: [pinned], nextCursor: null, hasMore: false })
    await loading
    expect(state.conversations.records.value[initial.id]?.pinnedAt).toBeNull()
    expect(sync.pagination.conversations.value.filter(c => c.id === initial.id)).toHaveLength(1)
  })

  it('discovers additional pinned pages after reconnecting a formerly complete list', async () => {
    const { backend, sync } = await fixture()
    expect(sync.pagination.hasMorePinned.value).toBe(false)
    const pin = { ...manual, id: 'synthetic-old-pin', pinnedAt: '2026-10-12T12:00:00Z' }
    const older = { ...pin, id: 'synthetic-older-pin', pinnedAt: '2026-10-11T12:00:00Z' }
    vi.spyOn(backend, 'page').mockImplementation(async (options) => options?.pinned === 'true'
      ? options.cursor
        ? { conversations: [older], nextCursor: null, hasMore: false }
        : { conversations: [pin], nextCursor: 'synthetic-pin-seek', hasMore: true }
      : { conversations: [initial], nextCursor: null, hasMore: false })
    await backend.refreshMetadata()
    expect(sync.pagination.hasMorePinned.value).toBe(true)
    await sync.pagination.loadMorePinned()
    expect(backend.page).toHaveBeenLastCalledWith({ pinned: 'true', cursor: 'synthetic-pin-seek' })
    expect(sync.pagination.conversations.value.filter(c => c.pinnedAt)).toHaveLength(2)
    expect(sync.pagination.hasMorePinned.value).toBe(false)
  })

  it('bounds the pinned window independently from normal pagination and metadata', async () => {
    const { state, backend, sync } = await fixture()
    for (let index = 0; index < 650; index++) backend.remember({ ...manual, id: `synthetic-pin-${index}`, pinnedAt: '2026-10-12T12:00:00Z' })
    expect(sync.pagination.pinnedWindowedList.value).toBe(true)
    expect(sync.pagination.conversations.value.filter(c => c.pinnedAt)).toHaveLength(500)
    expect(sync.pagination.conversations.value.some(c => c.id === initial.id)).toBe(true)
    expect(Object.keys(state.conversations.records.value).length).toBeLessThanOrEqual(600)
  }, 15_000)
})
