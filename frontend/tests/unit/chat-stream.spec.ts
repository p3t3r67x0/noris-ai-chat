import { afterEach, describe, expect, it, vi } from 'vitest'
import { useChatStream } from '../../app/composables/useChatStream'
import { createChatState } from '../../app/composables/useChat'
import { createMockTransport } from '../../app/lib/chat/mockTransport'
import type { ChatRequest, ChatTransport, StreamEvent } from '../../app/lib/chat/types'

const request: ChatRequest = { generationId: 'g', conversationId: 'c', inputMessageId: 'u', modelId: 'balanced', messages: [{ role: 'user', content: 'Hallo' }], attempt: 1 }
function scripted(events: readonly StreamEvent[]): ChatTransport {
  return { async *stream() { for (const event of events) yield event } }
}
function callbacks() { return { delta: vi.fn(), status: vi.fn() } }
afterEach(() => { vi.useRealTimers() })

describe('chat transport lifecycle', () => {
  it('goes through submitting and streaming to completed with deterministic chunks', async () => {
    vi.useFakeTimers()
    const stream = useChatStream(createMockTransport({ initialDelay: 100, chunkDelay: 20, chunkSize: 50 }))
    const calls = callbacks()
    const run = stream.start(request, calls)
    expect(stream.status.value).toBe('submitting')
    await vi.advanceTimersByTimeAsync(120)
    expect(stream.status.value).toBe('streaming')
    expect(calls.delta).toHaveBeenCalledTimes(1)
    await vi.runAllTimersAsync()
    await run
    expect(stream.status.value).toBe('completed')
    expect(stream.busy.value).toBe(false)
    expect(calls.status.mock.calls.map(([status]) => status)).toEqual(['submitting', 'streaming', 'completed'])
  })

  it('rejects a second send while submitting and preserves partial text on stop', async () => {
    vi.useFakeTimers()
    const stream = useChatStream(createMockTransport({ initialDelay: 100, chunkDelay: 20 }))
    const calls = callbacks()
    const run = stream.start(request, calls)
    expect(await stream.start(request, callbacks())).toBe(false)
    await vi.advanceTimersByTimeAsync(140)
    const count = calls.delta.mock.calls.length
    stream.stop()
    expect(stream.cancellationRequested.value).toBe(true)
    await run
    await vi.runAllTimersAsync()
    expect(stream.status.value).toBe('cancelled')
    expect(calls.delta).toHaveBeenCalledTimes(count)
    expect(count).toBeGreaterThan(0)
  })

  it('can cancel before the first event', async () => {
    vi.useFakeTimers()
    const stream = useChatStream(createMockTransport())
    const calls = callbacks()
    const run = stream.start(request, calls)
    stream.stop()
    await run
    expect(stream.status.value).toBe('cancelled')
    expect(calls.delta).not.toHaveBeenCalled()
  })

  it('retains partial output and reports a reproducible mock failure', async () => {
    const stream = useChatStream(createMockTransport({ clock: { wait: async () => {} } }))
    const calls = callbacks()
    await stream.start({ ...request, messages: [{ role: 'user', content: '/fehler' }] }, calls)
    expect(stream.status.value).toBe('failed')
    expect(stream.error.value).toContain('Bitte versuche es erneut')
    expect(calls.delta).toHaveBeenCalled()
  })

  it('does not accept text after a terminal event', async () => {
    const stream = useChatStream(scripted([{ seq: 1, type: 'response.started' }, { seq: 2, type: 'response.completed' }, { seq: 3, type: 'response.output_text.delta', delta: 'late' }]))
    const calls = callbacks()
    await stream.start(request, calls)
    expect(stream.status.value).toBe('completed')
    expect(calls.delta).not.toHaveBeenCalled()
  })

  it('ignores retransmitted events without duplicating text', async () => {
    const stream = useChatStream(scripted([{ seq: 1, type: 'response.started' }, { seq: 2, type: 'response.output_text.delta', delta: 'A' }, { seq: 2, type: 'response.output_text.delta', delta: 'A' }, { seq: 3, type: 'response.completed' }]))
    const calls = callbacks()
    await stream.start(request, calls)
    expect(calls.delta.mock.calls).toEqual([['A']])
  })

  it.each(([
    [{ seq: 2, type: 'response.started' }],
    [{ seq: 1, type: 'response.output_text.delta', delta: 'early' }],
    [{ seq: 1, type: 'response.started' }],
    [{ seq: 0, type: 'response.started' }],
  ] satisfies StreamEvent[][]).map(events => ({ events })))('fails closed on invalid or incomplete streams %j', async ({ events }) => {
    const stream = useChatStream(scripted(events))
    await stream.start(request, callbacks())
    expect(stream.status.value).toBe('failed')
    expect(stream.error.value).not.toBeNull()
    expect(stream.error.value).not.toContain('not iterable')
  })

  it('rejects oversized output before adding it to the message', async () => {
    const stream = useChatStream(scripted([{ seq: 1, type: 'response.started' }, { seq: 2, type: 'response.output_text.delta', delta: 'a'.repeat(262_145) }]))
    const calls = callbacks()
    await stream.start(request, calls)
    expect(stream.status.value).toBe('failed')
    expect(calls.delta).not.toHaveBeenCalled()
  })
})

describe('chat coordination', () => {
  it('creates one user and one reply for duplicate rapid sends', async () => {
    vi.useFakeTimers()
    let sequence = 0
    const chat = createChatState(createMockTransport(), { id: () => String(++sequence), now: () => '2026-10-09T12:00:00Z' })
    expect(chat.send('Hallo', 'balanced')).toBe(true)
    expect(chat.send('Hallo', 'balanced')).toBe(false)
    expect(chat.visible.value.map(message => message.role)).toEqual(['user', 'assistant'])
    await vi.runAllTimersAsync()
    expect(chat.visible.value.at(-1)?.status).toBe('completed')
  })

  it('keeps concurrent conversations isolated and blocks incompatible generations', async () => {
    vi.useFakeTimers()
    let sequence = 0
    const chat = createChatState(createMockTransport(), { id: () => String(++sequence) })
    chat.send('Erste Frage', 'balanced')
    const first = chat.conversations.activeId.value
    chat.newChat()
    expect(chat.visible.value).toEqual([])
    expect(chat.send('Zweite Frage', 'fast')).toBe(false)
    await vi.runAllTimersAsync()
    if (!first) throw new Error('Missing first conversation')
    chat.conversations.select(first)
    expect(chat.visible.value.at(-1)?.content).toContain('Erste Frage')
  })

  it('does not create conversations for empty or oversized input', () => {
    const chat = createChatState(scripted([]))
    expect(chat.send('  ', 'balanced')).toBe(false)
    expect(chat.send('x'.repeat(32_001), 'balanced')).toBe(false)
    expect(chat.conversations.visible.value).toHaveLength(0)
  })
})
