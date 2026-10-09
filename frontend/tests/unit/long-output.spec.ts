import { afterEach, describe, expect, it, vi } from 'vitest'
import { createRealTransport } from '../../app/lib/chat/realTransport'
import { CHAT_LIMITS, DEFAULT_CHAT_LIMITS, parseChatLimits } from '../../app/lib/chat/limits'
import { useChatStream } from '../../app/composables/useChatStream'
import { createChatState } from '../../app/composables/useChat'
import { parseChatSnapshot } from '../../app/lib/chat/persistence'
import type { ChatRequest, StreamEvent } from '../../app/lib/chat/types'

const request: ChatRequest = { generationId: 'long', conversationId: 'chat', inputMessageId: 'input', modelId: 'fixture-alpha', messages: [{ role: 'user', content: 'Hallo' }], attempt: 1 }
const text = ' token'.repeat(9000)
const encode = (event: StreamEvent) => `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`
function response(finish: 'stop' | 'length'): Response {
  const events: StreamEvent[] = [{ seq: 1, type: 'response.started' }]
  for (let offset = 0; offset < text.length; offset += 4096) events.push({ seq: events.length + 1, type: 'response.output_text.delta', delta: text.slice(offset, offset + 4096) })
  events.push(finish === 'stop' ? { seq: events.length + 1, type: 'response.completed' } : { seq: events.length + 1, type: 'response.failed', code: 'OUTPUT_LIMIT', message: 'Ausgabelimit erreicht.' })
  return new Response(events.map(encode).join(''), { headers: { 'Content-Type': 'text/event-stream' } })
}
afterEach(() => { Object.assign(CHAT_LIMITS, DEFAULT_CHAT_LIMITS); vi.useRealTimers() })

describe('Long output and safe configurable limits', () => {
  it.each(['stop', 'length'] as const)('keeps >8192 simulator tokens and the %s terminal state', async (finish) => {
    const chat = createChatState(createRealTransport({ fetcher: async url => String(url).endsWith('/chat') ? response(finish) : new Response('{}', { status: 503 }) }))
    expect(chat.send('Hallo', 'fixture-alpha')).toBe(true)
    await vi.waitFor(() => expect(chat.stream.busy.value).toBe(false))
    expect(chat.visible.value.at(-1)?.content).toBe(text)
    expect(chat.stream.status.value).toBe(finish === 'stop' ? 'completed' : 'failed')
    const saved = parseChatSnapshot(JSON.stringify(chat.snapshot()))
    expect(saved?.messages[chat.visible.value.at(-1)?.id ?? '']?.content).toBe(text)
    if (finish === 'length') {
      chat.retry('fixture-alpha')
      await vi.waitFor(() => expect(chat.stream.busy.value).toBe(false))
      expect(chat.variants(chat.visible.value.at(-1)?.id ?? '')).toHaveLength(2)
    }
  })
  it('checks UTF-16 output before appending a delta', async () => {
    CHAT_LIMITS.max_response_chars = 3
    const stream = useChatStream({ async *stream() {
      yield { seq: 1, type: 'response.started' }
      yield { seq: 2, type: 'response.output_text.delta', delta: '🌍' }
      yield { seq: 3, type: 'response.output_text.delta', delta: '🌍' }
    } })
    let received = ''
    await stream.start(request, { delta: delta => { received += delta }, status: () => {} })
    expect(received).toBe('🌍')
    expect(stream.status.value).toBe('failed')
  })
  it('enforces the configured aggregate byte limit', async () => {
    CHAT_LIMITS.max_stream_bytes = 1024
    const received = []
    for await (const event of createRealTransport({ fetcher: async () => response('stop') }).stream(request, new AbortController().signal)) received.push(event)
    expect(received.at(-1)).toMatchObject({ type: 'response.failed', code: 'INVALID_RESPONSE' })
  })
  it('honors the catalog total timeout beyond the old 135 seconds', async () => {
    vi.useFakeTimers()
    CHAT_LIMITS.stream_timeout_ms = 300_000
    CHAT_LIMITS.stream_idle_timeout_ms = 400_000
    const fetcher: typeof fetch = async (_, init) => await new Promise<Response>((_, reject) => { init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError'))) })
    const iterator = createRealTransport({ fetcher }).stream(request, new AbortController().signal)[Symbol.asyncIterator]()
    const pending = iterator.next()
    await vi.advanceTimersByTimeAsync(135_001)
    let resolved = false
    void pending.then(() => { resolved = true })
    await Promise.resolve()
    expect(resolved).toBe(false)
    await vi.advanceTimersByTimeAsync(164_999)
    expect(await pending).toMatchObject({ value: { type: 'response.failed', code: 'TIMEOUT' } })
    await iterator.return?.()
  })
  it('heartbeats reset idle timeout and Stop aborts the read', async () => {
    vi.useFakeTimers()
    const controller = new AbortController()
    let body: ReadableStreamDefaultController<Uint8Array> | undefined
    const fetcher: typeof fetch = async (_, init) => new Response(new ReadableStream<Uint8Array>({ start(value) {
      body = value
      init?.signal?.addEventListener('abort', () => value.error(new DOMException('aborted', 'AbortError')))
    } }), { headers: { 'Content-Type': 'text/event-stream' } })
    const iterator = createRealTransport({ fetcher, idleTimeoutMs: 100, timeoutMs: 1000 }).stream(request, controller.signal)[Symbol.asyncIterator]()
    const pending = iterator.next()
    for (let i = 0; i < 3; i++) {
      await vi.advanceTimersByTimeAsync(80)
      body?.enqueue(new TextEncoder().encode(': keepalive\n\n'))
      await vi.advanceTimersByTimeAsync(0)
    }
    controller.abort()
    expect(await pending).toMatchObject({ value: { type: 'response.cancelled' } })
    await iterator.return?.()
  })
  it('times out an idle response after headers', async () => {
    const fetcher: typeof fetch = async (_, init) => new Response(new ReadableStream<Uint8Array>({ start(value) {
      init?.signal?.addEventListener('abort', () => value.error(new DOMException('aborted', 'AbortError')))
    } }), { headers: { 'Content-Type': 'text/event-stream' } })
    const received = []
    for await (const event of createRealTransport({ fetcher, idleTimeoutMs: 5 }).stream(request, new AbortController().signal)) received.push(event)
    expect(received.at(-1)).toMatchObject({ type: 'response.failed', code: 'TIMEOUT' })
  })
  it('validates catalog limits and rejects unbounded policies', () => {
    expect(parseChatLimits(DEFAULT_CHAT_LIMITS)).toEqual(DEFAULT_CHAT_LIMITS)
    for (const limits of [{ ...DEFAULT_CHAT_LIMITS, max_response_chars: Infinity }, { ...DEFAULT_CHAT_LIMITS, stream_timeout_ms: 0 }, { ...DEFAULT_CHAT_LIMITS, max_stream_bytes: 67_108_865 }, {}]) expect(() => parseChatLimits(limits)).toThrow()
  })
})
