import { describe, expect, it, vi } from 'vitest'
import { createRealTransport, SSEFrames } from '../../app/lib/chat/realTransport'
import { createMockTransport } from '../../app/lib/chat/mockTransport'
import { useChatStream } from '../../app/composables/useChatStream'
import { createChatState } from '../../app/composables/useChat'
import type { ChatRequest, ChatTransport, StreamEvent } from '../../app/lib/chat/types'

const request: ChatRequest = { generationId: 'generation', conversationId: 'conversation', inputMessageId: 'input', modelId: 'fixture-alpha', messages: [{ role: 'user', content: 'Hallo' }], attempt: 1 }
const events: StreamEvent[] = [{ seq: 1, type: 'response.started' }, { seq: 2, type: 'response.output_text.delta', delta: 'Grüße 🌍' }, { seq: 3, type: 'response.completed' }]
const encode = (values: StreamEvent[]): string => values.map(event => `event: ${event.type}\r\ndata: ${JSON.stringify(event)}\r\n\r\n`).join('')
function response(text: string, size = 1): Response {
  const bytes = new TextEncoder().encode(text)
  return new Response(new ReadableStream<Uint8Array>({ start(controller) {
    for (let offset = 0; offset < bytes.length; offset += size) controller.enqueue(bytes.slice(offset, offset + size))
    controller.close()
  } }), { headers: { 'Content-Type': 'text/event-stream' } })
}

describe('Real transport and existing contract', () => {
  it.each([1, 2, 7, 8192])('decodes UTF-8 and SSE across chunks of %i bytes', async (size) => {
    const fetcher = vi.fn<typeof fetch>(async () => response(encode(events), size))
    const transport = createRealTransport({ fetcher })
    const received = []
    for await (const event of transport.stream(request, new AbortController().signal)) received.push(event)
    expect(received).toEqual(events)
    expect(fetcher.mock.calls[0]?.[0]).toBe('/api/v1/llm/chat')
    expect(fetcher.mock.calls[0]?.[1]?.credentials).toBe('same-origin')
    expect(JSON.parse(String(fetcher.mock.calls[0]?.[1]?.body))).toEqual(request)
    expect(fetcher.mock.calls[0]?.[1]?.headers).not.toHaveProperty('Authorization')
  })

  it.each(['mock', 'real'])('%s implements the same reducer contract', async (mode) => {
    const transport = mode === 'mock' ? createMockTransport({ clock: { wait: async () => {} } }) : createRealTransport({ fetcher: async () => response(encode(events)) })
    const stream = useChatStream(transport)
    let text = ''
    await stream.start(request, { delta: delta => { text += delta }, status: () => {} })
    expect(stream.status.value).toBe('completed')
    expect(text.length).toBeGreaterThan(0)
    expect(stream.busy.value).toBe(false)
  })

  it.each([
    [encode(events.slice(0, 2)), 'STREAM_INTERRUPTED'],
    ['data: invalid-json\n\n', 'INVALID_RESPONSE'],
    ['data: {"seq":1,"type":"unknown"}\n\n', 'INVALID_RESPONSE'],
    [encode([{ seq: 2, type: 'response.started' }]), 'INVALID_RESPONSE'],
    ['data: {"seq":1', 'INVALID_RESPONSE'],
  ])('fails incomplete or malformed streams without completing', async (text, code) => {
    const transport = createRealTransport({ fetcher: async () => response(text) })
    const received = []
    for await (const event of transport.stream(request, new AbortController().signal)) received.push(event)
    expect(received.at(-1)).toMatchObject({ type: 'response.failed', code })
    expect(received.some(event => event.type === 'response.completed')).toBe(false)
  })

  it('preserves a provider failure and partial text', async () => {
    const failure: StreamEvent = { seq: 3, type: 'response.failed', code: 'RATE_LIMIT', message: 'Bitte später versuchen.' }
    const stream = useChatStream(createRealTransport({ fetcher: async () => response(encode([...events.slice(0, 2), failure])) }))
    let text = ''
    await stream.start(request, { delta: delta => { text += delta }, status: () => {} })
    expect(text).toBe('Grüße 🌍')
    expect(stream.status.value).toBe('failed')
    expect(stream.error.value).toBe(failure.message)
  })

  it('sanitizes HTML proxy errors', async () => {
    const transport = createRealTransport({ fetcher: async () => new Response('secret-key and internal host', { status: 502 }) })
    const received = []
    for await (const event of transport.stream(request, new AbortController().signal)) received.push(event)
    expect(JSON.stringify(received)).not.toContain('secret')
    expect(received.at(-1)).toMatchObject({ type: 'response.failed', code: 'REQUEST_FAILED' })
  })

  it('cancels the fetch while waiting for headers', async () => {
    let observedSignal: AbortSignal | null = null
    const fetcher: typeof fetch = async (_, init) => await new Promise<Response>((_, reject) => {
      observedSignal = init?.signal ?? null
      observedSignal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    })
    const signal = new AbortController()
    const iterator = createRealTransport({ fetcher }).stream(request, signal.signal)[Symbol.asyncIterator]()
    const pending = iterator.next()
    signal.abort()
    expect(await pending).toMatchObject({ value: { seq: 1, type: 'response.cancelled' } })
    await iterator.return?.()
  })

  it('times out independently of user Stop', async () => {
    const fetcher: typeof fetch = async (_, init) => await new Promise<Response>((_, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    })
    const received = []
    for await (const event of createRealTransport({ fetcher, timeoutMs: 5 }).stream(request, new AbortController().signal)) received.push(event)
    expect(received.at(-1)).toMatchObject({ type: 'response.failed', code: 'TIMEOUT' })
  })

  it('handles SSE comments, multiline data and event buffer limits', () => {
    const parser = new SSEFrames()
    expect(parser.feed(': keepalive\ndata: first\ndata: second\n\n')).toEqual([{ event: null, data: 'first\nsecond' }])
    expect(() => parser.feed('x'.repeat(65_537))).toThrow()
  })

  it.each(['\r', '\r\n', '\n'])('dispatches the final SSE frame across single-character %j boundaries', (separator) => {
    const parser = new SSEFrames()
    const data = `event: response.completed${separator}data: {"seq":1,"type":"response.completed"}${separator}${separator}`
    const frames = [...data].flatMap(character => parser.feed(character))
    expect(frames).toEqual([{ event: 'response.completed', data: '{"seq":1,"type":"response.completed"}' }])
    expect(parser.incomplete).toBe(false)
  })

  it('uses only selected branch context for retry and model switching', async () => {
    const captured: ChatRequest[] = []
    let attempt = 0
    const transport: ChatTransport = createRealTransport({ fetcher: async (_, init) => {
      captured.push(JSON.parse(String(init?.body)) as ChatRequest)
      attempt += 1
      return response(encode(attempt === 1 ? [{ seq: 1, type: 'response.started' }, { seq: 2, type: 'response.failed', code: 'RATE_LIMIT', message: 'retry' }] : events))
    } })
    const chat = createChatState(transport)
    expect(chat.send('Original', 'fixture-alpha')).toBe(true)
    await vi.waitFor(() => expect(chat.stream.status.value).toBe('failed'))
    chat.retry('fixture-beta')
    await vi.waitFor(() => expect(chat.stream.status.value).toBe('completed'))
    expect(captured[1]?.modelId).toBe('fixture-beta')
    expect(captured[1]?.attempt).toBe(2)
    expect(captured[1]?.messages).toEqual([{ role: 'user', content: 'Original' }])
    const original = chat.visible.value[0]
    expect(original).toBeDefined()
    expect(chat.edit(original?.id ?? '', 'Edited', 'fixture-alpha')).toBe(true)
    await vi.waitFor(() => expect(captured).toHaveLength(3))
    expect(captured[2]?.messages).toEqual([{ role: 'user', content: 'Edited' }])
    expect(Object.values(chat.messages.value).some(message => message.content === 'Original')).toBe(true)
  })
})
