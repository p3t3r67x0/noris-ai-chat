import { describe, expect, it, vi } from 'vitest'
import { createWebSocketTransport } from '../../app/lib/chat/webSocketTransport'
import { ChatBackend } from '../../app/lib/chat/backend'
import { useChatStream } from '../../app/composables/useChatStream'
import type { ChatRequest } from '../../app/lib/chat/types'
import { applyToolProjection } from '../../app/lib/chat/toolEvents'
import type { ToolRunRecords } from '../../app/lib/chat/toolEvents'

class Socket extends EventTarget {
  static OPEN = 1
  static instances: Socket[] = []
  readyState = 0
  sent: Array<Record<string, unknown>> = []
  constructor(readonly url: string, readonly protocols: string[]) {
    super(); Socket.instances.push(this)
    setTimeout(() => { this.readyState = 1; this.dispatchEvent(new Event('open')) }, 0)
  }
  send(raw: string): void { this.sent.push(JSON.parse(raw)) }
  close(): void { this.readyState = 3; this.dispatchEvent(new Event('close')) }
  event(value: unknown): void { this.dispatchEvent(new MessageEvent('message', { data: JSON.stringify(value) })) }
}
const conversation = { id: crypto.randomUUID(), title: 'Thema', titleSource: 'fallback' as const, titleGenerationAttempted: true, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), archivedAt: null, activeLeafMessageId: null }
function request(): ChatRequest {
  const input = { id: crypto.randomUUID(), conversationId: conversation.id, parentMessageId: null, role: 'user' as const, content: 'Hallo', status: 'completed' as const, createdAt: conversation.createdAt }
  return { generationId: crypto.randomUUID(), conversationId: conversation.id, inputMessageId: input.id, assistantMessageId: crypto.randomUUID(), input, conversation, modelId: 'fixture-alpha', messages: [{ role: 'user', content: 'Must never be sent as history' }], attempt: 1 }
}
async function connected(): Promise<Socket> {
  for (let i = 0; i < 100; i++) {
    const socket = Socket.instances.at(-1)
    if (socket?.sent.length) return socket
    await new Promise(resolve => setTimeout(resolve, 10))
  }
  throw new Error('Socket did not send command')
}
function fixture() {
  Socket.instances = []
  const backend = new ChatBackend((async (path: string) => Response.json(path.endsWith('ws-ticket') ? { ticketId: 'one-time-test-ticket' } : { ...conversation, version: 1 })) as typeof fetch)
  return createWebSocketTransport({ backend, url: 'ws://localhost/api/v1/chat/ws', socket: Socket as unknown as typeof WebSocket })
}

describe('WebSocketTransport', () => {
  it('shares chat sequence with tool events and reconstructs an offline terminal snapshot', async () => {
    const transport = fixture()
    const input = request()
    let records: ToolRunRecords = {}
    transport.backend!.onToolState = next => { records = applyToolProjection(records, next) }
    const stream = useChatStream(transport)
    const running = stream.start(input, { delta: () => {}, status: () => {} })
    const socket = await connected()
    const envelope = { version: 1, generationId: input.generationId, conversationId: input.conversationId, messageId: input.assistantMessageId }
    const runId = crypto.randomUUID()
    const timestamp = new Date().toISOString()
    const payload = { runId, toolId: 'web.search.v1', state: 'running', lastSequence: 2, updatedAt: timestamp, cancelRequested: false, approval: null, result: null, errorCode: null }
    expect(socket.sent[0]?.toolEventVersion).toBe(1)
    socket.event({ ...envelope, type: 'chat.generation.started', seq: 1 })
    socket.event({ version: 1, eventVersion: 1, type: 'tool.started', generationId: input.generationId, conversationId: input.conversationId, runId, seq: 2, timestamp, payload })
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(records[runId]?.state).toBe('running')
    socket.close()
    await new Promise(resolve => setTimeout(resolve, 700))
    const resumed = await connected()
    resumed.event({ version: 1, eventVersion: 1, type: 'tool.snapshot', generationId: input.generationId, conversationId: input.conversationId, lastSequence: 5, timestamp,
      runs: [{ ...payload, state: 'succeeded', lastSequence: 4, result: { resultVersion: 1, sourceCount: 5 } }] })
    resumed.event({ ...envelope, type: 'chat.resume.snapshot', lastSequence: 5, content: 'Fertig', status: 'completed' })
    await running
    expect(records[runId]?.state).toBe('succeeded')
    expect(stream.status.value).toBe('completed')
    transport.dispose?.()
  })
  it('restores completed tools on a fresh page and filters unrelated generations', async () => {
    const transport = fixture()
    const generationId = crypto.randomUUID()
    const update = vi.fn()
    transport.backend!.onToolState = update
    await transport.observeTools?.(conversation.id, [generationId])
    const socket = await connected()
    expect(socket.sent[0]).toMatchObject({ type: 'chat.resume', generationId, lastReceivedSeq: 0, toolEventVersion: 1, toolEventsOnly: true })
    const run = { runId: crypto.randomUUID(), toolId: 'web.search.v1', state: 'cancelled', lastSequence: 7, updatedAt: new Date().toISOString(), cancelRequested: true, approval: null, result: null, errorCode: 'TOOL_CANCELLED' }
    const snapshot = { version: 1, eventVersion: 1, type: 'tool.snapshot', conversationId: conversation.id, generationId, lastSequence: 7, timestamp: run.updatedAt, runs: [run] }
    socket.event({ ...snapshot, generationId: crypto.randomUUID() })
    socket.event({ ...snapshot, conversationId: crypto.randomUUID() })
    expect(update).not.toHaveBeenCalled()
    socket.event(snapshot)
    expect(update).toHaveBeenCalledOnce()
    socket.event({ ...snapshot, lastSequence: 6, runs: [] })
    expect(update).toHaveBeenCalledOnce()
    await transport.observeTools?.(conversation.id, [generationId])
    expect(socket.sent).toHaveLength(2)
    expect(socket.sent[1]).toMatchObject({ type: 'chat.resume', generationId, toolEventVersion: 1, toolEventsOnly: true })
    transport.dispose?.()
  })
  it('keeps terminal tool delivery alive after chat completion and reconnects without replaying chat', async () => {
    const transport = fixture()
    const input = request()
    let records: ToolRunRecords = {}
    transport.backend!.onToolState = next => { records = applyToolProjection(records, next) }
    const stream = useChatStream(transport)
    const running = stream.start(input, { delta: () => {}, status: () => {} })
    const socket = await connected()
    const envelope = { version: 1, generationId: input.generationId, conversationId: input.conversationId, messageId: input.assistantMessageId }
    const runId = crypto.randomUUID()
    const timestamp = new Date().toISOString()
    const payload = { runId, toolId: 'web.search.v1', state: 'running', lastSequence: 2, updatedAt: timestamp, cancelRequested: false, approval: null, result: null, errorCode: null }
    socket.event({ ...envelope, type: 'chat.generation.started', seq: 1 })
    socket.event({ version: 1, eventVersion: 1, generationId: input.generationId, conversationId: input.conversationId, type: 'tool.started', runId, seq: 2, timestamp, payload })
    socket.event({ ...envelope, type: 'chat.generation.completed', seq: 3, content: 'Fertig' })
    await running
    const terminal = { ...payload, state: 'cancelled', lastSequence: 4, cancelRequested: true, errorCode: 'TOOL_CANCELLED' }
    socket.event({ version: 1, eventVersion: 1, generationId: input.generationId, conversationId: input.conversationId, type: 'tool.cancelled', runId, seq: 4, timestamp, payload: terminal })
    expect(records[runId]?.state).toBe('cancelled')
    expect(stream.status.value).toBe('completed')
    await transport.observeTools?.(input.conversationId, [input.generationId])
    expect(socket.sent.at(-1)).toMatchObject({ type: 'chat.resume', toolEventsOnly: true })
    socket.close()
    await vi.waitFor(() => expect(Socket.instances).toHaveLength(2))
    await transport.connect?.()
    const resumed = Socket.instances.at(-1)!
    expect(resumed.sent).toHaveLength(1)
    expect(resumed.sent[0]).toMatchObject({ type: 'chat.resume', generationId: input.generationId, toolEventsOnly: true })
    resumed.event({ version: 1, eventVersion: 1, type: 'tool.snapshot', conversationId: input.conversationId, generationId: input.generationId, lastSequence: 4, timestamp, runs: [terminal] })
    resumed.event({ version: 1, eventVersion: 1, generationId: input.generationId, conversationId: input.conversationId, type: 'tool.started', runId, seq: 2, timestamp, payload })
    expect(records[runId]?.state).toBe('cancelled')
    expect(stream.status.value).toBe('completed')
    transport.dispose?.()
  })
  it('buys a fresh authenticated ticket for each WSS connection on an HTTPS page', async () => {
    Socket.instances = []
    vi.stubGlobal('location', { protocol: 'https:', host: 'chat.oklabflensburg.de' })
    let issued = 0
    const fetcher = vi.fn(async () => Response.json({ ticketId: `fixture-ticket-${++issued}` }))
    const transport = createWebSocketTransport({ backend: new ChatBackend(fetcher), socket: Socket as unknown as typeof WebSocket })
    try {
      await transport.connect?.()
      const first = Socket.instances.at(-1)!
      expect(fetcher).toHaveBeenCalledWith('/api/v1/chat/ws-ticket', expect.objectContaining({ method: 'POST', credentials: 'same-origin', body: '{}' }))
      expect(first.url).toBe('wss://chat.oklabflensburg.de/api/v1/chat/ws')
      expect(first.protocols).toEqual(['noris-chat.v1', 'ticket.fixture-ticket-1'])
      first.close()
      await transport.connect?.()
      expect(Socket.instances.at(-1)!.protocols).toEqual(['noris-chat.v1', 'ticket.fixture-ticket-2'])
      expect(fetcher).toHaveBeenCalledTimes(2)
    }
    finally {
      transport.dispose?.()
      vi.unstubAllGlobals()
    }
  })
  it('streams before completion, ignores duplicates and sends references without history', async () => {
    const transport = fixture()
    const input = request()
    const stream = useChatStream(transport)
    let text = ''
    const running = stream.start(input, { delta: delta => { text += delta }, status: () => {} })
    const socket = await connected()
    expect(socket.protocols).toEqual(['noris-chat.v1', 'ticket.one-time-test-ticket'])
    expect(socket.url).not.toContain('ticket')
    expect(socket.sent[0]).not.toHaveProperty('messages')
    const envelope = { version: 1, generationId: input.generationId, conversationId: input.conversationId, messageId: input.assistantMessageId }
    socket.event({ ...envelope, type: 'chat.generation.started', seq: 1 })
    socket.event({ ...envelope, type: 'chat.generation.delta', seq: 2, delta: 'Hallo' })
    socket.event({ ...envelope, type: 'chat.generation.delta', seq: 2, delta: 'Hallo' })
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(text).toBe('Hallo')
    expect(stream.busy.value).toBe(true)
    socket.event({ ...envelope, type: 'chat.generation.completed', seq: 3, content: 'Hallo' })
    await running
    expect(text).toBe('Hallo')
    expect(stream.status.value).toBe('completed')
    transport.dispose?.()
  })
  it('reconnects with the last consumed sequence and replaces snapshots atomically', async () => {
    const transport = fixture()
    const input = request()
    const stream = useChatStream(transport)
    let text = ''
    const running = stream.start(input, { delta: delta => { text += delta }, replace: content => { text = content }, status: () => {} })
    const socket = await connected()
    const envelope = { version: 1, generationId: input.generationId, conversationId: input.conversationId, messageId: input.assistantMessageId }
    socket.event({ ...envelope, type: 'chat.generation.started', seq: 1 })
    socket.event({ ...envelope, type: 'chat.generation.delta', seq: 2, delta: 'Alt' })
    await new Promise(resolve => setTimeout(resolve, 0))
    socket.close()
    await new Promise(resolve => setTimeout(resolve, 700))
    const resumed = await connected()
    expect(resumed.sent[0]).toMatchObject({ type: 'chat.resume', lastReceivedSeq: 2 })
    resumed.event({ ...envelope, type: 'chat.resume.snapshot', lastSequence: 4, content: 'Autoritativer Text', status: 'completed' })
    await running
    expect(text).toBe('Autoritativer Text')
    expect(stream.status.value).toBe('completed')
    transport.dispose?.()
  })
  it('sends explicit cancellation and waits for the server terminal event', async () => {
    const transport = fixture()
    const input = request()
    const stream = useChatStream(transport)
    const running = stream.start(input, { delta: () => {}, status: () => {} })
    const socket = await connected()
    const envelope = { version: 1, generationId: input.generationId, conversationId: input.conversationId, messageId: input.assistantMessageId }
    socket.event({ ...envelope, type: 'chat.generation.started', seq: 1 })
    stream.stop()
    expect(socket.sent.at(-1)).toMatchObject({ type: 'chat.cancel', generationId: input.generationId })
    socket.event({ ...envelope, type: 'chat.generation.cancelled', seq: 2, content: '' })
    await running
    expect(stream.status.value).toBe('cancelled')
    transport.dispose?.()
  })
  it('keeps one streaming state across continuations and preserves the committed Stop text', async () => {
    const transport = fixture()
    const input = request()
    const stream = useChatStream(transport)
    let text = ''
    const statuses = vi.fn()
    const counts = vi.fn()
    const running = stream.start(input, { delta: delta => { text += delta }, replace: content => { text = content }, status: statuses, continuation: counts })
    const socket = await connected()
    const envelope = { version: 1, generationId: input.generationId, conversationId: input.conversationId, messageId: input.assistantMessageId }
    socket.event({ ...envelope, type: 'chat.generation.started', seq: 1, continuationCount: 0 })
    socket.event({ ...envelope, type: 'chat.generation.delta', seq: 2, delta: '# Antwort\n\n```python\n', continuationCount: 0 })
    socket.event({ ...envelope, type: 'chat.generation.delta', seq: 3, delta: '', continuationCount: 1 })
    socket.event({ ...envelope, type: 'chat.generation.delta', seq: 4, delta: 'print(1)\n', continuationCount: 1 })
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(stream.busy.value).toBe(true)
    expect(statuses.mock.calls.flat()).toEqual(['submitting', 'streaming'])
    stream.stop()
    socket.event({ ...envelope, type: 'chat.generation.delta', seq: 5, delta: 'print(2)\n', continuationCount: 1 })
    socket.event({ ...envelope, type: 'chat.generation.cancelled', seq: 6, content: '# Antwort\n\n```python\nprint(1)\nprint(2)\n', continuationCount: 1 })
    await running
    expect(text).toBe('# Antwort\n\n```python\nprint(1)\nprint(2)\n')
    expect(counts).toHaveBeenLastCalledWith(1)
    expect(statuses.mock.calls.flat()).toEqual(['submitting', 'streaming', 'cancelled'])
    expect(socket.sent.filter(command => command.type === 'chat.generate')).toHaveLength(1)
    transport.dispose?.()
  })
  it('restores continuation counts and limit messages from a terminal reconnect snapshot', async () => {
    const transport = fixture()
    const input = { ...request(), resume: true }
    const stream = useChatStream(transport)
    const replace = vi.fn()
    const failure = vi.fn()
    const continuation = vi.fn()
    const running = stream.start(input, { delta: () => {}, replace, status: () => {}, failure, continuation })
    const socket = await connected()
    socket.event({ version: 1, type: 'chat.resume.snapshot', generationId: input.generationId, conversationId: input.conversationId, messageId: input.assistantMessageId, lastSequence: 9, content: 'Erhaltener Text', status: 'incomplete', continuationCount: 2, code: 'AUTO_CONTINUATION_LIMIT', message: 'Limit für automatische Fortsetzungen erreicht.' })
    await running
    expect(replace).toHaveBeenCalledWith('Erhaltener Text')
    expect(continuation).toHaveBeenCalledWith(2)
    expect(failure).toHaveBeenCalledWith('AUTO_CONTINUATION_LIMIT', 'Das Limit für automatische Fortsetzungen ist erreicht. Der bisherige Text bleibt erhalten.', expect.objectContaining({ generationId: input.generationId }))
    expect(stream.status.value).toBe('incomplete')
    expect(stream.busy.value).toBe(false)
    transport.dispose?.()
  })
})

describe('conversation title metadata', () => {
  it('reconnects an idle tab and reads titles committed while disconnected', async () => {
    Socket.instances = []
    let titleSource: 'fallback' | 'generated' = 'fallback'
    const value = () => ({ ...conversation, version: titleSource === 'fallback' ? 1 : 2, titleSource, title: titleSource === 'fallback' ? 'Neuer Chat' : 'Docker DNS-Probleme' })
    const fetcher = vi.fn(async (path: string) => Response.json(path.endsWith('ws-ticket') ? { ticketId: 'fresh' } : { conversations: [value()] }))
    const backend = new ChatBackend(fetcher as typeof fetch)
    const update = vi.fn()
    backend.onConversation = update
    const transport = createWebSocketTransport({ backend, url: 'ws://localhost/chat', socket: Socket as unknown as typeof WebSocket })
    try {
      await transport.connect?.()
      const first = Socket.instances.at(-1)!
      first.event({ version: 1, type: 'chat.connected' })
      await vi.waitFor(() => expect(update).toHaveBeenCalledWith(expect.objectContaining({ titleSource: 'fallback' })))
      titleSource = 'generated'
      first.close()
      await vi.waitFor(() => expect(Socket.instances).toHaveLength(2))
      // The fake socket is registered in its constructor, before open and the
      // transport's message listener. A real server event arrives after open.
      await transport.connect?.()
      Socket.instances.at(-1)!.event({ version: 1, type: 'chat.connected' })
      await vi.waitFor(() => expect(update).toHaveBeenCalledWith(expect.objectContaining({ titleSource: 'generated', title: 'Docker DNS-Probleme' })))
      expect(fetcher.mock.calls.filter(([path]) => path.endsWith('ws-ticket'))).toHaveLength(2)
    }
    finally { transport.dispose?.() }
  })

  it('handles a standalone title event through versioned authority and protects manual titles', async () => {
    Socket.instances = []
    const manual = { ...conversation, version: 4, lastMessageAt: null, title: 'Mein manueller Titel', titleSource: 'manual' as const }
    const backend = new ChatBackend((async (path: string) => Response.json(path.endsWith('ws-ticket') ? { ticketId: 'fresh' } : manual)) as typeof fetch)
    const update = vi.fn()
    backend.onConversation = update
    backend.remember(manual)
    const transport = createWebSocketTransport({ backend, url: 'ws://localhost/chat', socket: Socket as unknown as typeof WebSocket })
    try {
      await transport.connect?.()
      const socket = Socket.instances.at(-1)!
      socket.event({ version: 1, type: 'chat.title.updated', conversationId: conversation.id, title: 'Verspäteter Titel', titleSource: 'generated' })
      await vi.waitFor(() => expect(update).toHaveBeenCalledTimes(2))
      socket.event({ version: 1, type: 'chat.conversation.updated', conversation: { ...conversation, version: 3, title: 'Alter Titel', titleSource: 'generated' } })
      expect(update).toHaveBeenCalledTimes(2)
      expect(update).toHaveBeenLastCalledWith(manual)
    }
    finally { transport.dispose?.() }
  })
})
