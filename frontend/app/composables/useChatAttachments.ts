import { computed, markRaw, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Ref } from 'vue'
import type { ChatBackend } from '../lib/chat/backend'
import type { Conversation } from '../lib/chat/conversations'
import type { ApiSchemas } from '../types/generated/api'
import { responseError, TransportError } from '../lib/chat/realTransport'
import { normalizeAppError } from '../lib/notifications/errors'
import type { ErrorDiagnostics } from '../lib/notifications/errors'
import { useAppNotifications } from './useAppNotifications'
import { CHAT_LIMITS } from '../lib/chat/limits'

export type ChatAttachment = ApiSchemas['AttachmentResponse']
export interface UploadEntry {
  key: string
  filename: string
  mime: string
  size: number
  status: 'uploading' | 'uploaded' | 'failed' | 'removing'
  progress: number
  error?: string
  errorCode?: string
  diagnostics?: ErrorDiagnostics
  attachment?: ChatAttachment
  reference?: ApiSchemas['TextReference']
  file?: File
}

const extensions: Record<string, string> = { txt: 'text/plain', md: 'text/markdown', markdown: 'text/markdown', pdf: 'application/pdf', png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg' }

export function useChatAttachments(backend: ChatBackend | undefined, active: Ref<Conversation | null>, ready: Ref<boolean>, createConversation: () => Conversation, supportsImages: Ref<boolean> = ref(false)) {
  const notifications = useAppNotifications()
  const records = ref<Record<string, UploadEntry[]>>({})
  const limits = ref<ApiSchemas['AttachmentLimitsResponse'] | null>(null)
  const error = ref<string | null>(null)
  const errorNotified = ref(false)
  const pending = new Map<string, XMLHttpRequest>()
  const files = computed(() => active.value ? records.value[active.value.id] ?? [] : [])
  const available = computed(() => Boolean(backend && ready.value && limits.value))
  const imageCompatible = computed(() => limits.value?.visionSupported === true && supportsImages.value)
  const blocked = computed(() => files.value.some(file => file.status !== 'uploaded' || !file.attachment?.modelUsable || (file.attachment.mimeType.startsWith('image/') && !imageCompatible.value)))
  const confirmed = computed(() => files.value.flatMap(file => file.attachment && file.status === 'uploaded' ? [file.attachment] : []))
  let revision = 0
  const localKey = 'noris-ai:attachments:v1'
  onMounted(() => {
    if (backend) return
    try {
      const saved = JSON.parse(localStorage.getItem(localKey) ?? '{}') as Record<string, UploadEntry[]>
      for (const [id, entries] of Object.entries(saved)) {
        if (Array.isArray(entries) && entries.length <= 10) records.value[id] = entries.filter(entry => entry.status === 'uploaded' && typeof entry.attachment?.textReference?.text === 'string' && entry.attachment.textReference.text.length <= CHAT_LIMITS.max_message_chars)
      }
    }
    catch { /* The local demo cache is optional. */ }
  })
  watch(records, value => {
    if (!backend) {
      try { localStorage.setItem(localKey, JSON.stringify(value)) }
      catch {
        if (!error.value) notifications?.reportError({ code: 'STORAGE_UNAVAILABLE' }, { operation: 'storage', resourceId: 'attachments' })
        errorNotified.value = true
        error.value = normalizeAppError({ code: 'STORAGE_UNAVAILABLE' }, { operation: 'storage' }).message
      }
    }
  }, { deep: true })

  async function refresh(): Promise<void> {
    if (!backend || !ready.value) return
    const current = ++revision
    const conversation = active.value
    try {
      limits.value ??= await backend.request<ApiSchemas['AttachmentLimitsResponse']>('/chat/attachments/limits')
      if (!conversation) return
      await backend.ensure(conversation)
      const result = await backend.request<ApiSchemas['AttachmentListResponse']>(`/chat/attachments?${new URLSearchParams({ conversationId: conversation.id })}`)
      if (current !== revision) return
      const local = records.value[conversation.id] ?? []
      // An in-flight response may have committed before XHR receives its ID.
      if (local.some(file => file.status === 'uploading' || file.status === 'removing')) return
      const restored = result.attachments.filter(a => !a.messageId && !local.some(file => file.attachment?.id === a.id)).map(a => ({ key: a.id, filename: a.originalFilename, mime: a.mimeType, size: a.sizeBytes, status: 'uploaded' as const, progress: 100, attachment: a }))
      records.value[conversation.id] = [...local, ...restored]
      error.value = null
      errorNotified.value = false
    }
    catch (cause) {
      if (current !== revision) return
      const context = { operation: 'attachments' as const, conversationId: conversation?.id ?? null, attemptId: String(current) }
      error.value = normalizeAppError(cause, context).message
      errorNotified.value = true
      notifications?.reportError(cause, context, { label: 'Anhänge neu laden', onClick: refresh })
    }
  }
  watch([() => active.value?.id, ready], () => { void refresh() }, { flush: 'post' })

  async function upload(entry: UploadEntry, conversation: Conversation): Promise<void> {
    if (!backend || !entry.file || !limits.value) return
    const context = { operation: 'upload' as const, conversationId: conversation.id, resourceId: entry.key, attemptId: crypto.randomUUID() }
    entry.status = 'uploading'; entry.progress = 0; delete entry.error; delete entry.errorCode
    const mime = entry.file.type || extensions[entry.filename.split('.').at(-1)?.toLowerCase() ?? ''] || ''
    try {
      if (!limits.value.mimeTypes.includes(mime)) throw new TransportError('ATTACHMENT_TYPE')
      if (!entry.size || entry.size > limits.value.maxFileBytes) throw new TransportError('ATTACHMENT_SIZE')
      await backend.ensure(conversation)
      if (!records.value[conversation.id]?.some(file => file.key === entry.key)) return
      await new Promise<void>((resolve, reject) => {
        const request = new XMLHttpRequest()
        pending.set(entry.key, request)
        request.open('POST', `/api/v1/chat/attachments?${new URLSearchParams({ conversationId: conversation.id, filename: entry.filename })}`)
        request.setRequestHeader('Content-Type', mime)
        request.setRequestHeader('Accept', 'application/json')
        request.timeout = 90_000
        request.upload.onprogress = event => { if (event.lengthComputable) entry.progress = Math.min(99, Math.round(event.loaded / event.total * 100)) }
        request.onload = () => {
          pending.delete(entry.key)
          if (request.status !== 201) {
            const requestId = request.getResponseHeader('X-Request-ID')
            void responseError(new Response(request.responseText, { status: request.status, ...(requestId ? { headers: { 'X-Request-ID': requestId } } : {}) })).then(reject, reject)
            return
          }
          try {
            const value = JSON.parse(request.responseText) as ChatAttachment
            if (!value.id || value.conversationId !== conversation.id || !['ready', 'stored'].includes(value.status)) throw new TransportError('INVALID_RESPONSE')
            entry.attachment = value; entry.status = 'uploaded'; entry.progress = 100
            resolve()
          }
          catch (cause) { reject(cause) }
        }
        request.onerror = () => { pending.delete(entry.key); reject(new TransportError('NETWORK_ERROR')) }
        request.ontimeout = () => { pending.delete(entry.key); reject(new TransportError('ATTACHMENT_UPLOAD_TIMEOUT')) }
        request.onabort = () => { pending.delete(entry.key); reject(new DOMException('Upload abgebrochen', 'AbortError')) }
        request.send(entry.file)
      })
    }
    catch (cause) {
      if (!records.value[conversation.id]?.some(file => file.key === entry.key) || (cause instanceof DOMException && cause.name === 'AbortError')) return
      const failure = normalizeAppError(cause, context)
      entry.status = 'failed'; entry.error = failure.message; entry.errorCode = failure.code; entry.diagnostics = failure.diagnostics
      // The retained card owns recovery; it is the only live announcement for uploads.
    }
  }
  async function add(selected: File[]): Promise<void> {
    if (!available.value || !limits.value) return
    error.value = null
    errorNotified.value = false
    if (files.value.length + selected.length > limits.value.maxFiles) { error.value = `Maximal ${limits.value.maxFiles} Dateien pro Nachricht.`; return }
    const conversation = active.value ?? createConversation()
    records.value[conversation.id] ??= []
    const list = records.value[conversation.id]!
    // Reserve all slots synchronously before starting asynchronous uploads.
    const added = selected.map(file => ({ key: crypto.randomUUID(), filename: file.name, mime: file.type || extensions[file.name.split('.').at(-1)?.toLowerCase() ?? ''] || '', size: file.size, status: 'uploading' as const, progress: 0, file: markRaw(file) }))
    list.push(...added)
    for (const entry of added) {
      const current = records.value[conversation.id]?.find(file => file.key === entry.key)
      if (current) await upload(current, conversation)
    }
  }
  async function uploadReference(entry: UploadEntry, conversation: Conversation): Promise<void> {
    if (!entry.reference) return
    entry.status = 'uploading'; delete entry.error
    try {
      const reference = entry.reference
      let attachment: ChatAttachment
      if (backend) {
        await backend.ensure(conversation)
        attachment = await backend.request<ChatAttachment>('/chat/attachments/references', 'POST', { ...reference, conversationId: conversation.id })
      }
      else {
        attachment = { id: entry.key, conversationId: conversation.id, messageId: null, originalFilename: 'Markierter Text', mimeType: 'text/plain', sizeBytes: entry.size, sha256: '', status: 'ready', extractionStatus: 'extracted', modelUsable: true, createdAt: new Date().toISOString(), textReference: reference }
      }
      entry.attachment = attachment; entry.status = 'uploaded'; entry.progress = 100
      delete entry.reference
    }
    catch (cause) {
      const failure = normalizeAppError(cause, { operation: 'upload', conversationId: conversation.id, resourceId: entry.key })
      entry.status = 'failed'; entry.error = failure.message; entry.errorCode = failure.code; entry.diagnostics = failure.diagnostics
    }
  }
  async function addReference(reference: ApiSchemas['TextReference']): Promise<void> {
    if (!reference.text.trim() || (backend && !ready.value)) return
    error.value = null
    errorNotified.value = false
    const maximum = limits.value?.maxReferenceChars ?? CHAT_LIMITS.max_message_chars
    if (reference.text.length > maximum) { error.value = `Die Textreferenz darf höchstens ${maximum.toLocaleString('de-DE')} Zeichen enthalten. Bitte wähle einen kürzeren Abschnitt.`; return }
    if (files.value.length >= (limits.value?.maxFiles ?? 10)) { error.value = `Maximal ${limits.value?.maxFiles ?? 10} Anhänge pro Nachricht.`; return }
    const conversation = active.value ?? createConversation()
    records.value[conversation.id] ??= []
    const key = crypto.randomUUID()
    records.value[conversation.id]!.push({ key, filename: 'Markierter Text', mime: 'text/plain', size: new TextEncoder().encode(reference.text).length, status: 'uploading', progress: 0, reference })
    const entry = records.value[conversation.id]!.find(file => file.key === key)!
    await uploadReference(entry, conversation)
  }
  async function remove(key: string): Promise<void> {
    const conversation = active.value
    const entry = files.value.find(file => file.key === key)
    if (!entry || !conversation) return
    pending.get(key)?.abort()
    if (entry.status === 'uploading' && entry.reference) return
    if (entry.attachment && backend) {
      entry.status = 'removing'
      try { await backend.request(`/chat/attachments/${entry.attachment.id}`, 'DELETE') }
      catch (cause) {
        entry.status = 'uploaded'
        const context = { operation: 'attachment-remove' as const, conversationId: conversation.id, resourceId: key, attemptId: crypto.randomUUID() }
        error.value = normalizeAppError(cause, context).message
        errorNotified.value = true
        notifications?.reportError(cause, context, { label: 'Erneut entfernen', onClick: () => remove(key) })
        return
      }
    }
    records.value[conversation.id] = files.value.filter(file => file.key !== key)
  }
  function retry(key: string): void {
    const entry = files.value.find(file => file.key === key)
    if (entry?.file && active.value) void upload(entry, active.value)
    else if (entry?.reference && active.value) void uploadReference(entry, active.value)
  }
  function sent(conversationId: string): void { records.value[conversationId] = [] }
  onUnmounted(() => { ++revision; for (const request of pending.values()) request.abort() })
  return { files, limits, error, errorNotified, available, blocked, imageCompatible, confirmed, add, addReference, remove, retry, refresh, sent }
}
