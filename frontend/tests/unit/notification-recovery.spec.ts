import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref, shallowRef } from 'vue'
import { ChatBackend } from '../../app/lib/chat/backend'
import { TransportError } from '../../app/lib/chat/realTransport'
import { useChatAttachments } from '../../app/composables/useChatAttachments'
import { createChatState } from '../../app/composables/useChat'
import { useChatBackend } from '../../app/composables/useChatBackend'
import { useChatStream } from '../../app/composables/useChatStream'
import { useModelSelection } from '../../app/composables/useModelSelection'
import { appNotificationsKey, createAppNotifications } from '../../app/composables/useAppNotifications'
import type { Conversation } from '../../app/lib/chat/conversations'
import type { ChatTransport } from '../../app/lib/chat/types'

const conversation: Conversation = { id: '10000000-0000-4000-8000-000000000001', title: 'Testchat', titleSource: 'manual', titleGenerationAttempted: true, activeLeafMessageId: null, archivedAt: null, createdAt: '2026-10-12T10:00:00Z', updatedAt: '2026-10-12T10:00:00Z' }
const wrappers: Array<{ unmount: () => void }> = []
const centers: ReturnType<typeof createAppNotifications>[] = []
afterEach(() => { wrappers.splice(0).forEach(wrapper => wrapper.unmount()); centers.splice(0).forEach(center => center.dispose()); localStorage.clear(); vi.unstubAllGlobals(); vi.useRealTimers() })
function notifications() {
  type Toast = Parameters<typeof createAppNotifications>[0]['toasts']['value'][number]
  const toasts = shallowRef<Toast[]>([])
  const add = vi.fn((options: Partial<Toast>): Toast => { const toast = { id: 'test', ...options } as Toast; toasts.value = [...toasts.value, toast]; return toast })
  const center = createAppNotifications({ toasts, add, remove: () => {} })
  centers.push(center)
  return { center, add, toasts }
}

describe('upload recovery through the existing attachment owner', () => {
  it.each(['NETWORK_ERROR', 'ATTACHMENT_UPLOAD_TIMEOUT', 'ATTACHMENT_TYPE'])('keeps the File and failed card for %s and retries the original bytes', async code => {
    const sent: unknown[] = []
    let count = 0
    class Xhr {
      upload = {}
      timeout = 0
      status = 0
      responseText = ''
      onload?: () => void
      onerror?: () => void
      ontimeout?: () => void
      onabort?: () => void
      open() {}
      setRequestHeader() {}
      getResponseHeader() { return 'request-1' }
      abort() { this.onabort?.() }
      send(file: File) {
        sent.push(file); count++
        queueMicrotask(() => {
          if (count === 1 && code === 'NETWORK_ERROR') { this.onerror?.(); return }
          if (count === 1 && code === 'ATTACHMENT_UPLOAD_TIMEOUT') { this.ontimeout?.(); return }
          this.status = count === 1 ? 400 : 201
          this.responseText = JSON.stringify(count === 1 ? { error: { code, message: 'secret internal stacktrace', request_id: 'request-1' } } : { id: 'file-id', conversationId: conversation.id, originalFilename: 'test.txt', status: 'ready', modelUsable: true, mimeType: 'text/plain' })
          this.onload?.()
        })
      }
    }
    vi.stubGlobal('XMLHttpRequest', Xhr)
    const backend = new ChatBackend()
    vi.spyOn(backend, 'ensure').mockResolvedValue(1)
    vi.spyOn(backend, 'request').mockImplementation(async path => path.endsWith('limits') ? { maxFiles: 10, maxFileBytes: 1000, mimeTypes: ['text/plain'] } : { attachments: [] })
    let attachments!: ReturnType<typeof useChatAttachments>
    const wrapper = mount(defineComponent({ setup() { attachments = useChatAttachments(backend, ref({ ...conversation }), ref(true), () => conversation); return () => h('div') } }))
    wrappers.push(wrapper)
    await attachments.refresh()
    const original = new File(['original text'], 'test.txt', { type: 'text/plain' })
    await attachments.add([original])
    const entry = attachments.files.value[0]!
    expect(entry.status).toBe('failed')
    expect(entry.errorCode).toBe(code)
    expect(entry.error).not.toMatch(/secret|stacktrace/)
    expect(entry.file).toBe(original)
    expect(attachments.blocked.value).toBe(true)
    expect(attachments.files.value).toHaveLength(1)
    if (code === 'ATTACHMENT_TYPE') expect(entry.diagnostics?.requestId).toBe('request-1')
    attachments.retry(entry.key)
    await flushPromises()
    expect(sent).toEqual([original, original])
    expect(entry.status).toBe('uploaded')
    expect(attachments.blocked.value).toBe(false)
  })
})

describe('chat state and notifications integration', () => {
  it('does not loop draft-save errors and retries the latest text through the existing owner', async () => {
    vi.useFakeTimers()
    const backend = new ChatBackend()
    vi.spyOn(backend, 'load').mockResolvedValue({ metadata: [], activeConversationId: null, path: null, drafts: { __new__: '' } })
    const draft = vi.spyOn(backend, 'draft').mockRejectedValueOnce(new TransportError('NETWORK_ERROR')).mockResolvedValue(undefined)
    const transport = { backend, stream: async function* () {} }
    let chat!: ReturnType<typeof createChatState>
    let sync!: ReturnType<typeof useChatBackend>
    const wrapper = mount(defineComponent({ setup() { chat = createChatState(transport); sync = useChatBackend(chat, transport); return () => h('div') } }))
    wrappers.push(wrapper)
    await flushPromises()
    chat.drafts.draft.value = 'First draft'
    await vi.advanceTimersByTimeAsync(350)
    expect(draft).toHaveBeenCalledOnce()
    await vi.advanceTimersByTimeAsync(1000)
    expect(draft).toHaveBeenCalledOnce()
    expect(sync.retryPersistence.value).not.toBeNull()
    chat.drafts.draft.value = 'Current draft'
    await sync.retryPersistence.value?.()
    expect(draft).toHaveBeenLastCalledWith('__new__', 'Current draft')
    await vi.advanceTimersByTimeAsync(350)
    expect(draft).toHaveBeenCalledTimes(2)
    expect(sync.storageWarning.value).toBeNull()
  })
  it('announces separate explicit model refresh failures and keeps a generation-triggered check quiet', async () => {
    const { center, toasts } = notifications()
    let selection!: ReturnType<typeof useModelSelection>
    const wrapper = mount(defineComponent({ setup() {
      selection = useModelSelection({ mode: 'real', fetcher: async () => { throw new TypeError('secret network error') } })
      return () => h('div')
    } }), { global: { provide: { [appNotificationsKey as symbol]: center } } })
    wrappers.push(wrapper)
    await flushPromises()
    expect(toasts.value).toHaveLength(1)
    await selection.refresh(false)
    expect(toasts.value).toHaveLength(1)
    await selection.refresh()
    expect(toasts.value).toHaveLength(2)
  })
  it('keeps settings failure in the existing state and retries only the affected chat', async () => {
    const { center, toasts } = notifications()
    const backend = new ChatBackend()
    vi.spyOn(backend, 'ensure').mockResolvedValue(1)
    const patch = vi.spyOn(backend, 'patch').mockRejectedValueOnce(new TransportError('TIMEOUT', 'secret', 'request-1')).mockResolvedValue(undefined)
    let chat!: ReturnType<typeof createChatState>
    const wrapper = mount(defineComponent({ setup() { chat = createChatState({ backend, stream: async function* () {} }); chat.conversations.records.value[conversation.id] = { ...conversation }; chat.conversations.select(conversation.id); return () => h('div') } }), { global: { provide: { [appNotificationsKey as symbol]: center } } })
    wrappers.push(wrapper)
    expect(await chat.setConversationMode('learning')).toBe(false)
    expect(chat.settingsError.value).toContain('zu lange')
    expect(toasts.value).toHaveLength(1)
    expect(patch).toHaveBeenCalledOnce()
    chat.conversations.create('anderer Chat')
    const retryAction = toasts.value[0]!.actions?.[0]?.onClick
    expect(typeof retryAction).toBe('function')
    if (typeof retryAction === 'function') retryAction(new MouseEvent('click'))
    await flushPromises()
    expect(patch).toHaveBeenLastCalledWith(conversation.id, { conversationMode: 'learning' })
    expect(chat.settingsError.value).toBeNull()
    expect(chat.conversations.activeId.value).toBe(conversation.id)
  })
  it('retains all messages and drafts if server deletion fails and deletes after explicit retry', async () => {
    const backend = new ChatBackend()
    vi.spyOn(backend, 'load').mockResolvedValue({ metadata: [], activeConversationId: null, path: null, drafts: {} })
    const remove = vi.spyOn(backend, 'remove').mockRejectedValueOnce(new TransportError('INTERNAL_ERROR')).mockResolvedValue(undefined)
    const transport = { backend, stream: async function* () {} }
    let chat!: ReturnType<typeof createChatState>
    let sync!: ReturnType<typeof useChatBackend>
    const wrapper = mount(defineComponent({ setup() { chat = createChatState(transport); sync = useChatBackend(chat, transport); return () => h('div') } }))
    wrappers.push(wrapper)
    await flushPromises()
    chat.conversations.records.value[conversation.id] = { ...conversation }
    chat.messages.value.message = { id: 'message', conversationId: conversation.id, parentMessageId: null, content: 'Preserve this text', role: 'assistant', status: 'completed', createdAt: conversation.createdAt }
    chat.drafts.records.value[conversation.id] = 'Preserve this draft'
    expect(sync.backendReady.value).toBe(true)
    await expect(chat.remove(conversation.id)).rejects.toMatchObject({ code: 'INTERNAL_ERROR' })
    expect(chat.messages.value.message?.content).toBe('Preserve this text')
    expect(chat.drafts.records.value[conversation.id]).toBe('Preserve this draft')
    await chat.remove(conversation.id)
    expect(chat.messages.value.message).toBeUndefined()
    expect(remove).toHaveBeenCalledTimes(2)
  })
  it.each(['TIMEOUT', 'RATE_LIMIT', 'MODEL_UNAVAILABLE', 'NETWORK_ERROR'])('preserves codes, request IDs and partial text when the transport throws %s', async code => {
    const transport: ChatTransport = { async *stream() { yield { type: 'response.started', seq: 1 }; yield { type: 'response.output_text.delta', seq: 2, delta: 'Partial text' }; throw new TransportError(code, 'secret text', 'request-1') } }
    const stream = useChatStream(transport)
    let text = ''
    await stream.start({ generationId: 'generation', conversationId: 'conversation', inputMessageId: 'user', modelId: 'model', messages: [], attempt: 1 }, { delta: delta => { text += delta }, status: () => {} })
    expect(stream.status.value).toBe('failed')
    expect(stream.errorCode.value).toBe(code)
    expect(stream.errorRequestId.value).toBe('request-1')
    expect(stream.error.value).not.toContain('secret')
    expect(text).toBe('Partial text')
  })
  it('keeps the saved text visible while a resume request is waiting', async () => {
    let resume!: () => void
    const transport: ChatTransport = { async *stream() { await new Promise<void>(resolve => { resume = resolve }); yield { type: 'response.snapshot', seq: 1, status: 'failed', content: 'Saved partial text', code: 'INTERRUPTED', message: 'secret' } } }
    const chat = createChatState(transport)
    chat.conversations.records.value[conversation.id] = { ...conversation, activeLeafMessageId: 'reply' }
    chat.conversations.select(conversation.id)
    chat.messages.value.user = { id: 'user', conversationId: conversation.id, parentMessageId: null, role: 'user', content: 'Question', status: 'completed', createdAt: conversation.createdAt }
    chat.messages.value.reply = { id: 'reply', conversationId: conversation.id, parentMessageId: 'user', role: 'assistant', content: 'Saved partial text', status: 'streaming', generationId: 'generation', createdAt: conversation.createdAt }
    chat.resume('reply')
    expect(chat.messages.value.reply.content).toBe('Saved partial text')
    resume(); await flushPromises()
    expect(chat.messages.value.reply.status).toBe('failed')
    expect(chat.messages.value.reply.content).toBe('Saved partial text')
    expect(chat.messages.value.reply.errorCode).toBe('INTERRUPTED')
  })
})
