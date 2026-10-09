import { CHAT_LIMITS, MAX_SNAPSHOT_CHARS } from '../lib/chat/limits'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { createConversationState } from './useConversations'
import type { ConversationDependencies } from './useConversations'
import { useChatStream } from './useChatStream'
import { visiblePath } from '../lib/chat/types'
import type { ChatMessage, ChatTransport, MessageRecords, ConversationTitleRequest } from '../lib/chat/types'
import { FALLBACK_TITLE, fallbackConversationTitle, TITLE_INPUT_LIMIT } from '../lib/chat/titles'
import { createConversationTitles } from './useConversationTitles'
import type { ChatModelId } from './useModelSelection'
import { useChatDrafts } from './useChatDrafts'
import { indexSiblingVariants, siblingVariants, variantLeaf } from '../lib/chat/branches'
import { CHAT_STORAGE_KEY, parseChatSnapshot } from '../lib/chat/persistence'
import type { ChatSnapshot } from '../lib/chat/persistence'
import { CONVERSATIONS_STORAGE_KEY, parseConversationSnapshot } from '../lib/chat/conversations'
import { useChatBackend } from './useChatBackend'

export function createChatState(transport: ChatTransport, dependencies: ConversationDependencies = {}, conversations = createConversationState(dependencies)) {
  const messages = ref<MessageRecords>({})
  const stream = useChatStream(transport)
  const id = dependencies.id ?? (() => globalThis.crypto.randomUUID())
  const now = dependencies.now ?? (() => new Date().toISOString())
  const visible = computed(() => conversations.active.value ? visiblePath(messages.value, conversations.active.value.id, conversations.active.value.activeLeafMessageId) : [])
  const generatingConversationId = ref<string | null>(null)
  const drafts = useChatDrafts(conversations.activeId)
  const preferredLeaves = ref<Record<string, string>>({})
  const titles = createConversationTitles(transport, conversationId => Object.hasOwn(conversations.records.value, conversationId) ? conversations.records.value[conversationId] : undefined)

  function rememberBranch(): void {
    const leaf = conversations.active.value?.activeLeafMessageId
    if (!leaf) return
    preferredLeaves.value = { ...preferredLeaves.value, ...Object.fromEntries(visible.value.map(message => [message.id, leaf])) }
  }

  function append(conversationId: string, parentMessageId: string | null, role: ChatMessage['role'], content: string): ChatMessage {
    const message: ChatMessage = { id: id(), conversationId, parentMessageId, role, content, status: role === 'user' ? 'completed' : 'submitting', createdAt: now() }
    messages.value = { ...messages.value, [message.id]: message }
    const conversation = conversations.records.value[conversationId]
    if (conversation) { conversation.activeLeafMessageId = message.id; conversation.updatedAt = message.createdAt }
    return messages.value[message.id] ?? message
  }

  function generate(input: ChatMessage, modelId: ChatModelId, attempt = 1, titleRequest?: ConversationTitleRequest): void {
    const history = visiblePath(messages.value, input.conversationId, input.id).map(({ role, content }) => ({ role, content }))
    const reply = append(input.conversationId, input.id, 'assistant', '')
    reply.modelId = modelId
    generatingConversationId.value = input.conversationId
    reply.generationId = id()
    reply.modelId = modelId
    void stream.start({ generationId: reply.generationId, conversationId: input.conversationId, inputMessageId: input.id, modelId, messages: history, attempt, input: { ...input }, assistantMessageId: reply.id, conversation: { ...conversations.records.value[input.conversationId]! } }, {
      delta: text => { reply.content += text },
      replace: text => { reply.content = text },
      status: next => {
        reply.status = next
        if (next === 'failed' && transport.backend && !reply.content) drafts.records.value[input.conversationId] = input.content
        if (next === 'streaming' && titleRequest) void titles.generate(titleRequest)
        const conversation = conversations.records.value[input.conversationId]
        if (next === 'completed' && messages.value[reply.id] === reply && conversation?.titleSource === 'fallback' && conversation.title === FALLBACK_TITLE) {
          const context = visiblePath(messages.value, input.conversationId, reply.id).map(message => message.content).join('\n')
          conversation.title = fallbackConversationTitle(context)
        }
      },
      failure: (code, message) => { reply.errorCode = code; reply.errorMessage = message },
    }).finally(() => { generatingConversationId.value = null })
  }

  function resume(messageId: string): void {
    const reply = messages.value[messageId]
    const input = reply?.parentMessageId ? messages.value[reply.parentMessageId] : undefined
    const conversation = reply ? conversations.records.value[reply.conversationId] : undefined
    if (!reply?.generationId || !input || !conversation || stream.busy.value) return
    generatingConversationId.value = conversation.id
    reply.content = ''
    void stream.start({ generationId: reply.generationId, conversationId: conversation.id, inputMessageId: input.id, assistantMessageId: reply.id, input: { ...input }, conversation: { ...conversation }, modelId: reply.modelId ?? '', messages: [], attempt: 1, resume: true }, {
      delta: text => { reply.content += text }, replace: text => { reply.content = text }, status: next => { reply.status = next },
    }).finally(() => { generatingConversationId.value = null })
  }

  function send(text: string, modelId: ChatModelId): boolean {
    const content = text.trim()
    if (stream.busy.value || !content || content.length > CHAT_LIMITS.max_message_chars) return false
    const draftConversationId = conversations.activeId.value
    const conversation = conversations.active.value ?? conversations.create()
    const parent = visible.value.at(-1)
    if (parent?.role === 'user') return false
    const needsTitle = conversation.activeLeafMessageId === null && !conversation.titleGenerationAttempted && conversation.titleSource === 'fallback'
    if (needsTitle) { conversation.title = fallbackConversationTitle(content); conversation.titleGenerationAttempted = true }
    const input = append(conversation.id, conversation.activeLeafMessageId, 'user', content)
    generate(input, modelId, 1, needsTitle ? { conversationId: conversation.id, inputMessageId: input.id, modelId, firstMessage: Array.from(content).slice(0, TITLE_INPUT_LIMIT).join('') } : undefined)
    drafts.clear(draftConversationId)
    return true
  }

  function newChat(): void { conversations.create() }
  function selectVariant(messageId: string): boolean {
    const message = Object.hasOwn(messages.value, messageId) ? messages.value[messageId] : undefined
    const conversation = conversations.active.value
    if (stream.busy.value || !message || !conversation || message.conversationId !== conversation.id) return false
    rememberBranch()
    conversation.activeLeafMessageId = variantLeaf(messages.value, preferredLeaves.value, messageId)
    return true
  }

  function regenerate(messageId: string, modelId: ChatModelId): boolean {
    if (stream.busy.value) return false
    const message = Object.hasOwn(messages.value, messageId) ? messages.value[messageId] : undefined
    if (!message || message.role !== 'assistant' || message.conversationId !== conversations.activeId.value || !message.parentMessageId) return false
    const input = messages.value[message.parentMessageId]
    if (!input || input.role !== 'user') return false
    rememberBranch()
    generate(input, modelId, siblingVariants(messages.value, messageId).length + 1)
    return true
  }

  function edit(messageId: string, text: string, modelId: ChatModelId): boolean {
    const content = text.trim()
    const original = Object.hasOwn(messages.value, messageId) ? messages.value[messageId] : undefined
    if (stream.busy.value || !content || content.length > CHAT_LIMITS.max_message_chars || original?.role !== 'user' || original.conversationId !== conversations.activeId.value) return false
    rememberBranch()
    const input = append(original.conversationId, original.parentMessageId, 'user', content)
    input.editedFromMessageId = original.id
    generate(input, modelId)
    return true
  }
  function retry(modelId: ChatModelId): void {
    if (stream.busy.value) return
    const last = visible.value.at(-1)
    if (last?.role !== 'assistant' || last.status !== 'failed' || !last.parentMessageId) return
    if (last.continuationCount) continueResponse(last.id, modelId)
    else regenerate(last.id, modelId)
  }

  function canContinue(messageId: string): boolean {
    const reply = Object.hasOwn(messages.value, messageId) ? messages.value[messageId] : undefined
    return !stream.busy.value && reply?.role === 'assistant'
      && reply.id === visible.value.at(-1)?.id && Boolean(reply.content)
      && ['incomplete', 'cancelled', 'failed'].includes(reply.status)
      && (reply.continuationCount ?? 0) < CHAT_LIMITS.max_continuations
      && reply.content.length < CHAT_LIMITS.max_response_chars
      && !['RESPONSE_SIZE_LIMIT', 'STREAM_SIZE_LIMIT', 'DUPLICATE_CONTINUATION'].includes(reply.errorCode ?? '')
  }

  function continueResponse(messageId: string, fallbackModelId: ChatModelId): boolean {
    if (!canContinue(messageId)) return false
    let reply = messages.value[messageId]!
    const source = reply
    if (!reply.parentMessageId) return false
    const modelId = reply.modelId ?? fallbackModelId
    const history = visiblePath(messages.value, reply.conversationId, reply.id).map(({ role, content }) => ({ role, content }))
    const continuationCount = (source.continuationCount ?? 0) + 1
    if (transport.backend) {
      rememberBranch()
      reply = append(source.conversationId, source.parentMessageId, 'assistant', source.content)
      reply.modelId = modelId
      reply.generationId = id()
    }
    reply.continuationCount = continuationCount
    delete reply.errorCode
    delete reply.errorMessage
    generatingConversationId.value = reply.conversationId
    void stream.start({ generationId: reply.generationId ?? id(), conversationId: reply.conversationId, inputMessageId: source.parentMessageId!, assistantMessageId: reply.id, modelId, messages: history, attempt: 1, operation: 'continue', continuationCount, ...(transport.backend ? { sourceAssistantMessageId: source.id, input: { ...messages.value[source.parentMessageId!]! }, conversation: { ...conversations.records.value[source.conversationId]! } } : {}) }, {
      delta: text => { reply.content += text },
      replace: text => { reply.content = text },
      status: next => { reply.status = next },
      failure: (code, message) => { reply.errorCode = code; reply.errorMessage = message },
    }).finally(() => { generatingConversationId.value = null })
    return true
  }
  function remove(conversationId: string): void {
    titles.cancel(conversationId)
    if (generatingConversationId.value === conversationId) stream.stop()
    messages.value = Object.fromEntries(Object.entries(messages.value).filter(([, message]) => message.conversationId !== conversationId))
    drafts.remove(conversationId)
    preferredLeaves.value = Object.fromEntries(Object.entries(preferredLeaves.value).filter(([node, leaf]) => Object.hasOwn(messages.value, node) && Object.hasOwn(messages.value, leaf)))
    conversations.remove(conversationId)
  }

  function snapshot(): ChatSnapshot { return { version: 1, conversations: conversations.snapshot(), messages: messages.value, drafts: drafts.records.value, preferredLeaves: preferredLeaves.value } }
  function hydrate(saved: ChatSnapshot): void {
    titles.cancelAll()
    conversations.hydrate(saved.conversations)
    messages.value = saved.messages
    drafts.records.value = saved.drafts
    preferredLeaves.value = saved.preferredLeaves
  }
  const variantIndex = computed(() => indexSiblingVariants(messages.value))
  const variants = (messageId: string): readonly ChatMessage[] => variantIndex.value.get(messageId) ?? []
  return { conversations, messages, visible, stream, titles, generatingConversationId, drafts, preferredLeaves, send, retry, canContinue, continueResponse, newChat, remove, selectVariant, regenerate, edit, variants, snapshot, hydrate, resume }
}

export function useChat(transport: ChatTransport) {
  const state = createChatState(transport)
  if (transport.backend) {
    const persistence = useChatBackend(state, transport)
    return { ...state, ...persistence }
  }
  const storageWarning = ref<string | null>(null)
  let stopWatching: (() => void) | undefined
  let timer: ReturnType<typeof setTimeout> | undefined
  let persistenceAllowed = true
  function flush(): void {
    clearTimeout(timer)
    timer = undefined
    if (!persistenceAllowed) return
    try {
      const serialized = JSON.stringify(state.snapshot())
      if (serialized.length > MAX_SNAPSHOT_CHARS) throw new Error('Speichergrenze erreicht')
      window.localStorage.setItem(CHAT_STORAGE_KEY, serialized)
    }
    catch { storageWarning.value = 'Änderungen können gerade nicht lokal gespeichert werden.' }
  }
  function externalChange(event: StorageEvent): void {
    if (event.key !== CHAT_STORAGE_KEY) return
    persistenceAllowed = false
    state.titles.dispose()
    storageWarning.value = 'Chats wurden in einem anderen Tab geändert. Lade diese Seite neu, um den aktuellen Stand zu verwenden.'
  }
  function pageHidden(): void { state.titles.cancelAll(); flush() }
  onMounted(() => {
    try {
      const raw = window.localStorage.getItem(CHAT_STORAGE_KEY)
      if (raw) {
        const saved = parseChatSnapshot(raw)
        if (saved) state.hydrate(saved)
        else { persistenceAllowed = false; storageWarning.value = 'Gespeicherte Chats konnten nicht geladen werden. Der bisherige Speicher bleibt erhalten.' }
      }
      else {
        const legacy = window.localStorage.getItem(CONVERSATIONS_STORAGE_KEY)
        const metadata = legacy ? parseConversationSnapshot(legacy) : null
        if (metadata) {
          for (const conversation of Object.values(metadata.conversations)) conversation.activeLeafMessageId = null
          state.conversations.hydrate(metadata)
        }
      }
    }
    catch { storageWarning.value = 'Lokaler Speicher ist nicht verfügbar.' }
    const schedule = () => {
      timer ??= setTimeout(flush, 120)
    }
    // Draft keystrokes must not traverse every stored message. Both watchers
    // schedule the same atomic snapshot, so persistence/recovery is unchanged.
    const stopData = watch([state.conversations.records, state.conversations.activeId, state.messages, state.preferredLeaves], schedule, { deep: true, flush: 'sync' })
    const stopDrafts = watch(state.drafts.records, schedule, { deep: true, flush: 'sync' })
    stopWatching = () => { stopData(); stopDrafts() }
    window.addEventListener('pagehide', pageHidden)
    window.addEventListener('storage', externalChange)
  })
  onUnmounted(() => {
    state.stream.stop()
    state.titles.dispose()
    stopWatching?.()
    if (typeof window !== 'undefined') {
      if (timer !== undefined) flush()
      window.removeEventListener('pagehide', pageHidden)
      window.removeEventListener('storage', externalChange)
    }
  })
  return { ...state, storageWarning, backendReady: ref(true), importAvailable: ref(false), importBusy: ref(false), importLocalChats: async () => {} }
}
