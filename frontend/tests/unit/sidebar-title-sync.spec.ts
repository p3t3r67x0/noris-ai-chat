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

async function fixture(initialValue = initial) {
  Socket.instances = []
  let authority = initialValue
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
  it('keeps prepared metadata hidden and reveals an authoritative update without a reload', async () => {
    const { wrapper, socket, state } = await fixture({ ...initial, sidebarVisible: false })
    expect(wrapper.findAll('button')).toHaveLength(0)
    socket.event({ version: 1, type: 'chat.conversation.updated', conversation: { ...generated, sidebarVisible: true } })
    await vi.waitFor(() => expect(wrapper.get('button').attributes('title')).toBe(generated.title))
    expect(state.conversations.records.value[initial.id]?.sidebarVisible).toBe(true)
  })

  it('new chat preserves the draft and existing metadata without posting a conversation', async () => {
    const { state, fetcher, sync } = await fixture()
    const previous = JSON.stringify(state.conversations.records.value)
    state.drafts.draft.value = 'Mein neuer Entwurf'
    state.newChat()
    state.newChat()
    expect(state.conversations.activeId.value).toBeNull()
    expect(state.drafts.draft.value).toBe('Mein neuer Entwurf')
    expect(JSON.stringify(state.conversations.records.value)).toBe(previous)
    expect(sync.pagination.conversations.value).toHaveLength(1)
    expect(fetcher.mock.calls.some(([url, options]) => String(url) === '/api/v1/conversations' && options?.method === 'POST')).toBe(false)
  })
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
})
