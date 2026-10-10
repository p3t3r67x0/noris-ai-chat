import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { createChatState, useChat } from '../../app/composables/useChat'
import { createMockTransport } from '../../app/lib/chat/mockTransport'
import { createRealTransport } from '../../app/lib/chat/realTransport'
import { parseChatSnapshot, CHAT_STORAGE_KEY } from '../../app/lib/chat/persistence'
import { automaticTitleCandidates, fallbackConversationTitle, mockConversationTitle, normalizeAutomaticTitle, validGeneratedTitle } from '../../app/lib/chat/titles'
import type { ConversationTitleRequest, ConversationTitleResponse } from '../../app/lib/chat/types'

function fixture(chunkSize = 32_000) {
  vi.useFakeTimers()
  let id = 0
  const calls: { request: ConversationTitleRequest, signal: AbortSignal, resolve: (value: ConversationTitleResponse) => void, reject: (error: Error) => void }[] = []
  const transport = createMockTransport({ initialDelay: 10, chunkDelay: 10, chunkSize })
  transport.generateTitle = (request, signal) => new Promise((resolve, reject) => { calls.push({ request, signal, resolve, reject }) })
  const chat = createChatState(transport, { id: () => `id-${++id}` })
  function resolve(index: number, title = 'Docker Compose Einrichtung', update: Partial<ConversationTitleResponse> = {}) {
    const call = calls[index]!
    call.resolve({ conversationId: call.request.conversationId, inputMessageId: call.request.inputMessageId, title, ...update })
  }
  return { chat, calls, resolve, transport }
}
afterEach(() => { vi.useRealTimers(); localStorage.clear() })

describe('bounded conversation titles', () => {
  it.each([
    ['Welche Vorteile bietet Rust gegenüber C++?', 'Rust vs. C++'],
    ['Warum funktioniert Docker DNS nicht?', 'Docker DNS-Probleme'],
    ['How do I configure Docker Compose?', 'Docker Compose Setup'],
    ['Wie installiere ich Noris AI mit Docker?', 'Noris AI Docker-Setup'],
    ['Erkläre die Unterschiede zwischen PostgreSQL und MariaDB.', 'PostgreSQL vs. MariaDB'],
  ])('mock titles preserve language and technical terms: %s', (input, title) => {
    expect(mockConversationTitle(input)).toBe(title)
    expect(validGeneratedTitle(title)).toBe(true)
  })

  it.each(['', 'x'.repeat(51), 'eins zwei drei vier fünf sechs sieben', 'Unterhaltung', 'Wie Docker funktioniert', 'Hello world', '"Docker Setup"', 'Docker Setup.', 'Docker\nSetup', 'Docker 😀', 'Docker\u202eSetup', '<script>', 'Kontakt test@example.com', 'Passwort token=synthetic', 'https://example.com'])('rejects invalid or sensitive generated title: %j', (title) => {
    expect(validGeneratedTitle(title)).toBe(false)
  })

  it('shows the message and streams before the background title resolves', async () => {
    const { chat, calls, resolve } = fixture(100)
    expect(chat.send('Wie installiere ich Docker Compose?', 'balanced')).toBe(true)
    const conversation = chat.conversations.active.value!
    expect(conversation.title).toBe('Docker Compose Einrichtung')
    expect(conversation.titleGenerationAttempted).toBe(true)
    expect(chat.visible.value[0]?.content).toBe('Wie installiere ich Docker Compose?')
    expect(calls).toHaveLength(0)
    await vi.advanceTimersByTimeAsync(20)
    expect(calls).toHaveLength(1)
    expect(chat.visible.value.at(-1)?.content.length).toBeGreaterThan(0)
    expect(chat.stream.status.value).toBe('streaming')
    const messages = JSON.stringify(chat.messages.value)
    resolve(0)
    await vi.advanceTimersByTimeAsync(0)
    expect(conversation.title).toBe('Docker Compose Einrichtung')
    expect(conversation.titleSource).toBe('generated')
    expect(JSON.stringify(chat.messages.value)).toBe(messages)
    await vi.advanceTimersByTimeAsync(100)
    expect(chat.stream.status.value).toBe('completed')
  })

  it('sends only a Unicode-safe bounded first message and never regenerates on follow-up or edit', async () => {
    const { chat, calls, resolve } = fixture()
    const input = 'Rust ' + '𐐀'.repeat(1100)
    chat.send(input, 'balanced')
    await vi.advanceTimersByTimeAsync(100)
    expect(Array.from(calls[0]!.request.firstMessage)).toHaveLength(1024)
    expect(Object.keys(calls[0]!.request).sort()).toEqual(['conversationId', 'firstMessage', 'inputMessageId', 'modelId'])
    expect(chat.visible.value[0]?.content).toBe(input)
    resolve(0, 'Rust Unicode Verarbeitung')
    await vi.advanceTimersByTimeAsync(0)
    chat.send('Noch eine Frage', 'fast')
    await vi.advanceTimersByTimeAsync(100)
    chat.edit(chat.visible.value[0]!.id, 'Geänderte Frage', 'balanced')
    await vi.advanceTimersByTimeAsync(100)
    expect(calls).toHaveLength(1)
  })

  it('manual rename wins before and after generation', async () => {
    const { chat, resolve } = fixture()
    chat.send('Docker Compose', 'balanced')
    const conversation = chat.conversations.active.value!
    await vi.advanceTimersByTimeAsync(20)
    chat.conversations.rename(conversation.id, 'Meine Docker-Notizen')
    resolve(0)
    await vi.advanceTimersByTimeAsync(100)
    expect(conversation.title).toBe('Meine Docker-Notizen')
    expect(conversation.titleSource).toBe('manual')
    chat.newChat()
    chat.send('Docker Compose', 'balanced')
    await vi.advanceTimersByTimeAsync(100)
    resolve(1)
    await vi.advanceTimersByTimeAsync(0)
    const second = chat.conversations.active.value!
    expect(second.titleSource).toBe('generated')
    chat.conversations.rename(second.id, 'Eigener Titel')
    expect(second.titleSource).toBe('manual')
    expect(second.title).toBe('Eigener Titel')
  })

  it('does not request a title for a chat renamed before its first message', async () => {
    const { chat, calls } = fixture()
    chat.newChat()
    chat.conversations.rename(chat.conversations.activeId.value!, 'Vorgegebener Titel')
    chat.send('Docker', 'balanced')
    await vi.advanceTimersByTimeAsync(100)
    expect(calls).toHaveLength(0)
  })

  it('assigns out-of-order titles to their own chats even after switching and archiving', async () => {
    const { chat, resolve } = fixture()
    chat.send('Docker', 'balanced')
    const first = chat.conversations.active.value!
    await vi.advanceTimersByTimeAsync(100)
    chat.newChat()
    chat.send('Rust', 'balanced')
    const second = chat.conversations.active.value!
    await vi.advanceTimersByTimeAsync(100)
    chat.conversations.select(first.id)
    chat.conversations.archive(second.id)
    resolve(1, 'Rust vs. C++')
    resolve(0, 'Docker Compose Einrichtung')
    await vi.advanceTimersByTimeAsync(0)
    expect(first.title).toBe('Docker Compose Einrichtung')
    expect(second.title).toBe('Rust vs. C++')
    expect(second.archivedAt).not.toBeNull()
    expect(chat.conversations.activeId.value).toBe(first.id)
  })

  it('keeps a title request independent of Stop on the chat answer', async () => {
    const { chat, calls, resolve } = fixture()
    chat.send('Docker', 'balanced')
    await vi.advanceTimersByTimeAsync(10)
    chat.stream.stop()
    await vi.advanceTimersByTimeAsync(0)
    expect(chat.stream.status.value).toBe('cancelled')
    expect(calls[0]!.signal.aborted).toBe(false)
    resolve(0)
    await vi.advanceTimersByTimeAsync(0)
    expect(chat.conversations.active.value?.titleSource).toBe('generated')
  })

  it('deleting cancels the request and late results never restore a chat', async () => {
    const { chat, calls, resolve } = fixture()
    chat.send('Docker', 'balanced')
    const id = chat.conversations.activeId.value!
    await vi.advanceTimersByTimeAsync(20)
    chat.remove(id)
    expect(calls[0]!.signal.aborted).toBe(true)
    resolve(0)
    await vi.advanceTimersByTimeAsync(100)
    expect(chat.conversations.records.value[id]).toBeUndefined()
    expect(Object.values(chat.messages.value)).toHaveLength(0)
  })

  it.each(['conversationId', 'inputMessageId'] as const)('discards a response with the wrong %s', async (field) => {
    const { chat, resolve } = fixture()
    chat.send('Docker', 'balanced')
    await vi.advanceTimersByTimeAsync(100)
    resolve(0, 'Docker Compose Einrichtung', { [field]: 'wrong-id' })
    await vi.advanceTimersByTimeAsync(0)
    expect(chat.conversations.active.value?.titleSource).toBe('fallback')
  })

  it.each(['TIMEOUT', 'BUDGET_LIMIT', 'RATE_LIMIT', 'PROVIDER_UNREACHABLE', 'MODEL_UNAVAILABLE', 'INVALID_RESPONSE'])('preserves fallback and chat completion after %s, without retries', async (error) => {
    const { chat, calls } = fixture()
    chat.send('Docker', 'balanced')
    await vi.advanceTimersByTimeAsync(20)
    calls[0]!.reject(new Error(error))
    await vi.advanceTimersByTimeAsync(100)
    expect(chat.stream.status.value).toBe('completed')
    expect(chat.stream.error.value).toBeNull()
    expect(chat.conversations.active.value?.title).toBe('Neuer Chat')
    chat.send('Weitere Frage', 'balanced')
    await vi.advanceTimersByTimeAsync(10_000)
    expect(calls).toHaveLength(1)
  })

  it('aborts at its own timeout and rejects a late successful result', async () => {
    const { chat, calls, resolve } = fixture()
    chat.send('Docker', 'balanced')
    await vi.advanceTimersByTimeAsync(8100)
    expect(calls[0]!.signal.aborted).toBe(true)
    expect(chat.stream.status.value).toBe('completed')
    resolve(0)
    await vi.advanceTimersByTimeAsync(0)
    expect(chat.conversations.active.value?.titleSource).toBe('fallback')
  })

  it('bounds simultaneous background requests without a retry queue', async () => {
    const { chat, calls } = fixture()
    for (let i = 0; i < 3; i++) {
      chat.newChat()
      chat.send('Docker', 'balanced')
      await vi.advanceTimersByTimeAsync(100)
    }
    expect(calls).toHaveLength(2)
    expect(chat.conversations.active.value?.titleGenerationAttempted).toBe(true)
    await vi.advanceTimersByTimeAsync(10_000)
    expect(calls).toHaveLength(2)
  })

  it('persists generated titles and attempted fallbacks; reload and switching do not regenerate', async () => {
    const { chat, calls, resolve, transport } = fixture()
    chat.send('Docker', 'balanced')
    await vi.advanceTimersByTimeAsync(100)
    resolve(0)
    await vi.advanceTimersByTimeAsync(0)
    chat.newChat()
    chat.send('Rust', 'balanced')
    await vi.advanceTimersByTimeAsync(100)
    const snapshot = parseChatSnapshot(JSON.stringify(chat.snapshot()))!
    const reloaded = createChatState(transport)
    reloaded.hydrate(snapshot)
    for (const conversation of Object.values(snapshot.conversations.conversations)) reloaded.conversations.select(conversation.id)
    await vi.advanceTimersByTimeAsync(0)
    expect(calls).toHaveLength(2)
    expect(reloaded.conversations.visible.value.map(item => [item.title, item.titleSource, item.titleGenerationAttempted])).toContainEqual(['Docker Compose Einrichtung', 'generated', true])
    expect(reloaded.conversations.visible.value.map(item => [item.title, item.titleSource, item.titleGenerationAttempted])).toContainEqual(['Neuer Chat', 'fallback', true])
  })

  it('migrates old snapshots without changing names or generating titles retroactively', async () => {
    const { chat, calls, transport } = fixture()
    chat.newChat()
    const id = chat.conversations.activeId.value!
    const legacy = JSON.parse(JSON.stringify(chat.snapshot()))
    delete legacy.conversations.conversations[id].titleSource
    delete legacy.conversations.conversations[id].titleGenerationAttempted
    legacy.conversations.conversations[id].title = 'Mein bisheriger Gesprächstitel'
    const snapshot = parseChatSnapshot(JSON.stringify(legacy))!
    const reloaded = createChatState(transport)
    reloaded.hydrate(snapshot)
    reloaded.send('Docker', 'balanced')
    await vi.advanceTimersByTimeAsync(100)
    expect(reloaded.conversations.active.value?.title).toBe('Mein bisheriger Gesprächstitel')
    expect(reloaded.conversations.active.value?.titleSource).toBe('manual')
    expect(calls).toHaveLength(0)
    legacy.conversations.conversations[id].titleSource = 'invalid'
    expect(parseChatSnapshot(JSON.stringify(legacy))).toBeNull()
  })

  it('cancels pending results on hydrate, pagehide and unmount and flushes the attempt marker', async () => {
    const { calls, resolve, transport } = fixture()
    const wrapper = mount(defineComponent({ setup() { return useChat(transport) }, render() { return h('div') } }))
    wrapper.vm.send('Docker', 'balanced')
    await vi.advanceTimersByTimeAsync(100)
    window.dispatchEvent(new Event('pagehide'))
    expect(calls[0]!.signal.aborted).toBe(true)
    const saved = parseChatSnapshot(localStorage.getItem(CHAT_STORAGE_KEY)!)!
    expect(Object.values(saved.conversations.conversations)[0]?.titleGenerationAttempted).toBe(true)
    resolve(0)
    await vi.advanceTimersByTimeAsync(0)
    expect(wrapper.vm.conversations.active.value?.titleSource).toBe('fallback')
    wrapper.vm.newChat()
    wrapper.vm.send('Rust', 'balanced')
    await vi.advanceTimersByTimeAsync(100)
    wrapper.vm.hydrate(parseChatSnapshot(JSON.stringify(wrapper.vm.snapshot()))!)
    expect(calls[1]!.signal.aborted).toBe(true)
    wrapper.vm.newChat()
    wrapper.vm.send('Docker', 'balanced')
    await vi.advanceTimersByTimeAsync(100)
    wrapper.unmount()
    expect(calls[2]!.signal.aborted).toBe(true)
  })

  it('uses the same-origin backend contract and sanitizes proxy failures', async () => {
    const request: ConversationTitleRequest = { conversationId: 'c', inputMessageId: 'u', modelId: 'balanced', firstMessage: 'Docker' }
    const signal = new AbortController().signal
    const fetcher = vi.fn<typeof fetch>(async () => Response.json({ conversationId: 'c', inputMessageId: 'u', title: 'Docker Compose Einrichtung' }))
    const transport = createRealTransport({ fetcher })
    expect(await transport.generateTitle!(request, signal)).toMatchObject({ title: 'Docker Compose Einrichtung' })
    expect(fetcher.mock.calls[0]).toEqual(['/api/v1/llm/conversation-title', expect.objectContaining({ method: 'POST', credentials: 'same-origin', signal, body: JSON.stringify(request) })])
    const failing = createRealTransport({ fetcher: async () => new Response('synthetic-secret', { status: 502 }) })
    await expect(failing.generateTitle!(request, signal)).rejects.toThrow('Modellanfrage')
    const invalid = createRealTransport({ fetcher: async () => Response.json({ conversationId: 'wrong', inputMessageId: 'u', title: 'Docker Setup' }) })
    await expect(invalid.generateTitle!(request, signal)).rejects.toThrow()
  })

  it.each(['Docker DNS', 'Docker DNS Troubleshooting', 'Fiktive Beispiele sammeln', 'Add MCP to Codex now', 'ÖPNV & Mobilität', 'Datenbankzugriffsrechte prüfen'])('accepts concise topics with two to five words: %s', (title) => {
    expect(validGeneratedTitle(title)).toBe(true)
  })

  it.each(['Docker', 'eins zwei drei vier fünf sechs', 'A'.repeat(38) + ' BB', 'Docker DNS...', 'Docker DNS…', 'Bitte Docker erklären', 'Kannst du Docker erklären', 'Can you explain Docker', 'Docker\tDNS', 'Docker  DNS', 'Docker DNS:', 'Docker DNS;'])('rejects unsuitable title: %s', (title) => {
    expect(validGeneratedTitle(title)).toBe(false)
  })

  it.each([
    ['Automatisierte Chat-Titel Implementierung', 'Automatische Chat-Titel'],
    ['Automatisierte Chat-Titel Impl...', 'Automatische Chat-Titel'],
    ['Kannst du mir helfen, eine automatische Chat-Titelgenerierung für Noris AI zu implementieren und dabei die bestehende Architektur zu erhalten?', 'Automatische Chat-Titel'],
    ['Kannst du mir erklären, wie ich Docker unter Ubuntu mit nftables konfigurieren kann?', 'Docker und nftables'],
    ['Unbekannte Frage '.repeat(2000), 'Neuer Chat'],
    ['Wie steht es damit?', 'Neuer Chat'],
  ])('normalizes automatic topics without fragments or ellipsis: %s', (input, title) => {
    expect(normalizeAutomaticTitle(input)).toBe(title)
    expect(fallbackConversationTitle(input)).toBe(title)
  })

  it('keeps known technical nouns when choosing a narrower candidate', () => {
    expect(automaticTitleCandidates('Docker DNS Troubleshooting Guide')).toContain('Docker DNS')
    expect(normalizeAutomaticTitle('und wie steht es aus sicht der...', 'Wir besprechen Docker und nftables.')).toBe('Docker und nftables')
  })

  it('does not interpret an incidental brand in code as a Noris AI integration topic', () => {
    expect(fallbackConversationTitle('Docker\nEin Beispiel: greet("noris")')).toBe('Neuer Chat')
  })

  it('normalizes historical automatic titles locally while preserving manual names, messages and branches', async () => {
    const { chat, transport, calls } = fixture()
    chat.send('Docker und nftables', 'balanced')
    await vi.advanceTimersByTimeAsync(100)
    const original = chat.snapshot()
    const automatic = chat.conversations.active.value!
    automatic.title = 'und wie steht es aus sicht der...'
    automatic.titleSource = 'generated'
    chat.newChat()
    const manual = chat.conversations.active.value!
    chat.conversations.rename(manual.id, 'Automatisierte Chat-Titel Implementierung – Meine vollständigen Notizen')
    const restored = parseChatSnapshot(JSON.stringify(chat.snapshot()))!
    expect(restored.conversations.conversations[automatic.id]?.title).toBe('Docker und nftables')
    expect(restored.conversations.conversations[manual.id]?.title).toBe(manual.title)
    expect(restored.messages).toEqual(original.messages)
    expect(restored.preferredLeaves).toEqual(original.preferredLeaves)
    const reloaded = createChatState(transport)
    reloaded.hydrate(restored)
    await vi.advanceTimersByTimeAsync(100)
    expect(calls).toHaveLength(1)
  })

  it('never applies a stale width adjustment to a renamed title', () => {
    const { chat } = fixture()
    chat.newChat()
    const conversation = chat.conversations.active.value!
    conversation.title = 'Docker DNS Troubleshooting Guide'
    conversation.titleSource = 'generated'
    chat.conversations.fitTitle(conversation.id, conversation.title, 'Docker DNS')
    expect(conversation.title).toBe('Docker DNS')
    chat.conversations.rename(conversation.id, 'Meine eigenen langen DNS-Notizen bleiben vollständig erhalten')
    chat.conversations.fitTitle(conversation.id, 'Docker DNS', 'Neuer Chat')
    expect(conversation.titleSource).toBe('manual')
    expect(conversation.title).toBe('Meine eigenen langen DNS-Notizen bleiben vollständig erhalten')
  })

  it('recovers a vague first question from the completed conversation locally without a second title request', async () => {
    const { chat, transport, calls } = fixture()
    transport.stream = async function* () {
      yield { seq: 1, type: 'response.started' }
      yield { seq: 2, type: 'response.output_text.delta', delta: 'Das Thema ist Docker unter Ubuntu mit nftables.' }
      yield { seq: 3, type: 'response.completed' }
    }
    chat.send('was kann ich unter dem begriff verstehen?', 'balanced')
    expect(chat.conversations.active.value?.title).toBe('Neuer Chat')
    await vi.advanceTimersByTimeAsync(0)
    expect(chat.conversations.active.value?.title).toBe('Docker und nftables')
    expect(chat.conversations.active.value?.titleSource).toBe('fallback')
    calls[0]!.reject(new Error('INVALID_RESPONSE'))
    await vi.advanceTimersByTimeAsync(0)
    chat.send('und wie steht es aus sicht der Sicherheit?', 'balanced')
    await vi.advanceTimersByTimeAsync(100)
    expect(calls).toHaveLength(1)
    expect(chat.conversations.active.value?.title).toBe('Docker und nftables')
  })
})
