import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createChatState } from '../../app/composables/useChat'
import { useChatStream } from '../../app/composables/useChatStream'
import { CHAT_LIMITS, DEFAULT_CHAT_LIMITS, applyChatLimits, ABSOLUTE_MESSAGE_CHARS } from '../../app/lib/chat/limits'
import { parseChatSnapshot } from '../../app/lib/chat/persistence'
import { createRealTransport, parseStreamEvent } from '../../app/lib/chat/realTransport'
import type { ChatRequest, ChatTransport } from '../../app/lib/chat/types'
import MarkdownContent from '../../app/components/chat/MarkdownContent'
import ChatMessage from '../../app/components/chat/ChatMessage.vue'

afterEach(() => { Object.assign(CHAT_LIMITS, DEFAULT_CHAT_LIMITS); vi.useRealTimers() })

function fixture(options: { stop?: boolean, failure?: string } = {}) {
  const requests: ChatRequest[] = []
  const original = '# Titel\n\n```python\n' + "print('alt')\n".repeat(3000)
  const continuation = "print('neu')\n```\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n- Punkt\n\n> Zitat\n\n" + 'Absatz '.repeat(5000)
  const transport: ChatTransport = { async *stream(request, signal) {
    requests.push(structuredClone(request))
    yield { seq: 1, type: 'response.started' }
    yield { seq: 2, type: 'response.output_text.delta', delta: request.operation === 'continue' ? continuation : original }
    if (options.stop && request.operation === 'continue') {
      await new Promise<void>(resolve => { if (signal.aborted) resolve(); else signal.addEventListener('abort', () => resolve(), { once: true }) })
      yield { seq: 3, type: 'response.cancelled' }
    }
    else if (options.failure && request.operation === 'continue') yield { seq: 3, type: 'response.failed', code: options.failure, message: 'Fortsetzung fehlgeschlagen.' }
    else yield { seq: 3, type: 'response.incomplete', reason: 'output_limit' }
  } }
  Object.assign(CHAT_LIMITS, { max_response_chars: 300_000 })
  let id = 0
  const chat = createChatState(transport, { id: () => `id-${++id}` })
  const settle = async () => { await vi.waitFor(() => expect(chat.stream.busy.value).toBe(false)) }
  return { chat, requests, original, continuation, settle }
}

describe('long responses and explicit continuation', () => {
  it('continues multiple times in the same assistant without extra branches or automatic calls', async () => {
    const { chat, requests, original, continuation, settle } = fixture()
    chat.send('Frage', 'fixture-alpha'); await settle()
    const reply = chat.visible.value[1]!
    const id = reply.id
    expect(reply.status).toBe('incomplete')
    expect(reply.content).toBe(original)
    expect(requests).toHaveLength(1)
    expect(chat.continueResponse(id, 'different-model')).toBe(true)
    expect(chat.continueResponse(id, 'different-model')).toBe(false)
    await settle()
    expect(reply.content).toBe(original + continuation)
    expect(chat.continueResponse(id, 'different-model')).toBe(true); await settle()
    expect(reply.content).toBe(original + continuation + continuation)
    expect(Object.keys(chat.messages.value)).toHaveLength(2)
    expect(chat.visible.value[1]?.id).toBe(id)
    expect(chat.variants(id)).toHaveLength(1)
    expect(requests).toHaveLength(3)
    expect(requests[2]).toMatchObject({ operation: 'continue', assistantMessageId: id, inputMessageId: chat.visible.value[0]!.id, continuationCount: 2, modelId: 'fixture-alpha' })
    expect(requests[2]?.messages.at(-1)?.content).toBe(original + continuation)
  })

  it('keeps all previous and new text when Stop interrupts a continuation', async () => {
    const { chat, original, continuation, settle } = fixture({ stop: true })
    chat.send('Frage', 'fixture-alpha'); await settle()
    const reply = chat.visible.value[1]!
    chat.continueResponse(reply.id, 'fixture-alpha')
    await vi.waitFor(() => expect(reply.content).toBe(original + continuation))
    chat.stream.stop(); await settle()
    expect(reply.status).toBe('cancelled')
    expect(reply.content).toBe(original + continuation)
    expect(reply.errorCode).toBeUndefined()
    expect(chat.canContinue(reply.id)).toBe(true)
  })

  it.each(['NETWORK_ERROR', 'TIMEOUT', 'BUDGET_LIMIT', 'PROVIDER_ERROR'])('persists precise %s failures and keeps continuation retry on the same node', async (failure) => {
    const { chat, requests, original, continuation, settle } = fixture({ failure })
    chat.send('Frage', 'fixture-alpha'); await settle()
    const reply = chat.visible.value[1]!
    chat.continueResponse(reply.id, 'fixture-alpha'); await settle()
    expect(reply).toMatchObject({ status: 'failed', errorCode: failure, errorMessage: 'Fortsetzung fehlgeschlagen.' })
    expect(reply.content).toBe(original + continuation)
    chat.retry('another-model'); await settle()
    expect(Object.keys(chat.messages.value)).toHaveLength(2)
    expect(requests.at(-1)?.operation).toBe('continue')
  })

  it('restores long text, continuation metadata and selected variants after reload', async () => {
    const { chat, original, continuation, settle } = fixture()
    chat.send('Frage', 'fixture-alpha'); await settle()
    const oldReply = chat.visible.value[1]!
    chat.continueResponse(oldReply.id, 'fixture-alpha'); await settle()
    chat.regenerate(oldReply.id, 'fixture-beta'); await settle()
    const sibling = chat.visible.value[1]!
    chat.selectVariant(oldReply.id)
    const restored = fixture().chat
    const snapshot = parseChatSnapshot(JSON.stringify(chat.snapshot()))
    expect(snapshot).not.toBeNull()
    restored.hydrate(snapshot!)
    expect(restored.visible.value[1]).toMatchObject({ id: oldReply.id, content: original + continuation, status: 'incomplete', continuationCount: 1, modelId: 'fixture-alpha' })
    expect(restored.canContinue(oldReply.id)).toBe(true)
    restored.selectVariant(sibling.id)
    expect(restored.visible.value[1]?.content).toBe(original)
    expect(restored.visible.value[1]?.modelId).toBe('fixture-beta')
  })

  it('reload during continuation keeps the entire partial answer and marks it stopped', async () => {
    const { chat, original, continuation, settle } = fixture({ stop: true })
    chat.send('Frage', 'fixture-alpha'); await settle()
    const reply = chat.visible.value[1]!
    chat.continueResponse(reply.id, 'fixture-alpha')
    await vi.waitFor(() => expect(reply.content).toBe(original + continuation))
    const saved = parseChatSnapshot(JSON.stringify(chat.snapshot()))!
    expect(saved.messages[reply.id]).toMatchObject({ status: 'cancelled', content: original + continuation, continuationCount: 1 })
    chat.stream.stop(); await settle()
  })

  it('rejects continuations of ancestors or inactive branches and respects step and size caps', async () => {
    const { chat, settle } = fixture()
    chat.send('Frage', 'fixture-alpha'); await settle()
    const reply = chat.visible.value[1]!
    chat.send('Nachfrage', 'fixture-alpha'); await settle()
    expect(chat.continueResponse(reply.id, 'fixture-alpha')).toBe(false)
    const leaf = chat.visible.value.at(-1)!
    leaf.continuationCount = CHAT_LIMITS.max_continuations
    expect(chat.continueResponse(leaf.id, 'fixture-alpha')).toBe(false)
    leaf.continuationCount = 0
    CHAT_LIMITS.max_response_chars = leaf.content.length
    expect(chat.continueResponse(leaf.id, 'fixture-alpha')).toBe(false)
    chat.newChat()
    expect(chat.continueResponse(leaf.id, 'fixture-alpha')).toBe(false)
  })

  it('renders one complete code block and all long Markdown structures after continuation', async () => {
    const { original, continuation } = fixture()
    const wrapper = mount(MarkdownContent, { props: { content: original }, global: { stubs: { CodeBlock: true } } })
    expect(wrapper.findAllComponents({ name: 'CodeBlock' })).toHaveLength(1)
    await wrapper.setProps({ content: original + continuation })
    expect(wrapper.get('h1').text()).toBe('Titel')
    expect(wrapper.findAllComponents({ name: 'CodeBlock' })).toHaveLength(1)
    expect(wrapper.getComponent({ name: 'CodeBlock' }).props('code')).toBe("print('alt')\n".repeat(3000) + "print('neu')\n")
    expect(wrapper.findAll('td').map(cell => cell.text())).toEqual(['1', '2'])
    expect(wrapper.get('li').text()).toBe('Punkt')
    expect(wrapper.get('blockquote').text()).toBe('Zitat')
    expect(wrapper.text()).toContain('Absatz '.repeat(4999).trim())
    wrapper.unmount()
  })

  it('batches streaming Markdown renders and immediately flushes the complete terminal text', async () => {
    vi.useFakeTimers()
    const wrapper = mount(MarkdownContent, { props: { content: '', streaming: true } })
    await wrapper.setProps({ content: '# Anfang' })
    await wrapper.setProps({ content: '# Neuester Stand' })
    expect(wrapper.text()).toBe('')
    expect(wrapper.emitted('rendered')).toBeUndefined()
    await vi.advanceTimersByTimeAsync(50)
    expect(wrapper.get('h1').text()).toBe('Neuester Stand')
    expect(wrapper.emitted('rendered')).toHaveLength(1)
    await wrapper.setProps({ content: '# Vollständig', streaming: false })
    expect(wrapper.get('h1').text()).toBe('Vollständig')
    expect(wrapper.emitted('rendered')).toHaveLength(2)
    await vi.runAllTimersAsync()
    expect(wrapper.get('h1').text()).toBe('Vollständig')
    wrapper.unmount()
  })

  it('shows an explicit continuation action and precise persisted errors', async () => {
    const { chat, settle } = fixture()
    chat.send('Frage', 'fixture-alpha'); await settle()
    const reply = chat.visible.value[1]!
    const wrapper = mount(ChatMessage, { props: { message: reply, canContinue: true }, global: { stubs: { UButton: { props: ['label'], emits: ['click'], template: '<button @click="$emit(\'click\')">{{ label }}</button>' }, MessageVariants: true, MarkdownContent: true } } })
    expect(wrapper.text()).toContain('Ausgabelimit erreicht – weiterschreiben')
    await wrapper.findAll('button').find(button => button.text() === 'Weiterschreiben')!.trigger('click')
    expect(wrapper.emitted('continue')).toHaveLength(1)
    reply.status = 'failed'; reply.errorMessage = 'Kontextlimit erreicht.'
    await wrapper.setProps({ message: { ...reply } })
    expect(wrapper.text()).toContain('Kontextlimit erreicht.')
    expect(wrapper.text()).not.toContain('Antwort nicht abgeschlossen')
    wrapper.unmount()
  })
})

describe('negotiated limits and bounded streaming', () => {
  it('preserves large input drafts and explicitly rejects oversized replacements without truncation', () => {
    const { chat } = fixture()
    CHAT_LIMITS.max_message_chars = 100_000
    const text = 'Eingabe '.repeat(10_000)
    chat.drafts.draft.value = text
    expect(chat.drafts.draft.value).toBe(text)
    expect(Object.values(parseChatSnapshot(JSON.stringify(chat.snapshot()))!.drafts)).toContain(text)
    chat.drafts.draft.value = 'x'.repeat(ABSOLUTE_MESSAGE_CHARS * 2 + 1)
    expect(chat.drafts.draft.value).toBe(text)
    expect(chat.drafts.error.value).toContain('bisherige Entwurf wurde erhalten')
    chat.drafts.draft.value = 'Korrigiert'
    expect(chat.drafts.error.value).toBeNull()
  })

  it('accepts server limits for long generation and rejects unbounded catalog values', () => {
    applyChatLimits({ ...DEFAULT_CHAT_LIMITS, max_message_chars: 600_000, max_response_chars: 500_000, stream_timeout_ms: 920_000 })
    expect(CHAT_LIMITS.stream_timeout_ms).toBe(920_000)
    expect(CHAT_LIMITS.max_message_chars).toBe(600_000)
    expect(() => applyChatLimits({ ...DEFAULT_CHAT_LIMITS, max_response_chars: Number.MAX_SAFE_INTEGER })).toThrow()
    expect(() => applyChatLimits({ ...DEFAULT_CHAT_LIMITS, stream_timeout_ms: Infinity })).toThrow()
    expect(parseStreamEvent({ event: 'response.incomplete', data: '{"seq":3,"type":"response.incomplete","reason":"output_limit"}' })).toMatchObject({ type: 'response.incomplete' })
    expect(() => parseStreamEvent({ event: null, data: '{"seq":3,"type":"response.incomplete","reason":"unknown"}' })).toThrow()
  })

  it('uses the advertised total timeout instead of the previous fixed 135 seconds', async () => {
    vi.useFakeTimers()
    CHAT_LIMITS.stream_timeout_ms = 920_000
    const fetcher: typeof fetch = async (_, init) => await new Promise<Response>((_, reject) => init?.signal?.addEventListener('abort', () => reject(new DOMException('abort', 'AbortError'))))
    const request: ChatRequest = { generationId: 'g', conversationId: 'c', inputMessageId: 'u', modelId: 'alpha', messages: [{ role: 'user', content: 'x' }], attempt: 1 }
    const stream = useChatStream(createRealTransport({ fetcher }))
    const promise = stream.start(request, { delta: () => {}, status: () => {} })
    await vi.advanceTimersByTimeAsync(136_000)
    expect(stream.busy.value).toBe(true)
    await vi.advanceTimersByTimeAsync(784_000)
    await promise
    expect(stream.errorCode.value).toBe('TIMEOUT')
  })

  it('times out a quiet downstream connection separately from the total timeout', async () => {
    vi.useFakeTimers()
    const fetcher: typeof fetch = async (_, init) => new Response(new ReadableStream({ start(controller) { init?.signal?.addEventListener('abort', () => controller.error(new DOMException('abort', 'AbortError'))) } }), { headers: { 'Content-Type': 'text/event-stream' } })
    const request: ChatRequest = { generationId: 'g', conversationId: 'c', inputMessageId: 'u', modelId: 'alpha', messages: [{ role: 'user', content: 'x' }], attempt: 1 }
    const received: unknown[] = []
    const run = (async () => { for await (const event of createRealTransport({ fetcher, idleTimeoutMs: 50, timeoutMs: 1000 }).stream(request, new AbortController().signal)) received.push(event) })()
    await vi.advanceTimersByTimeAsync(50); await run
    expect(received.at(-1)).toMatchObject({ type: 'response.failed', code: 'TIMEOUT' })
  })
})
