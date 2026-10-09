import { describe, expect, it } from 'vitest'
import { createWebSocketTransport } from '../../app/lib/chat/webSocketTransport'
import { ChatBackend } from '../../app/lib/chat/backend'
import { useChatStream } from '../../app/composables/useChatStream'
import type { ChatRequest } from '../../app/lib/chat/types'

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
})
