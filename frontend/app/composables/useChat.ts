import type { ApiSchemas } from '../types/generated/api'
import { CHAT_LIMITS, MAX_SNAPSHOT_CHARS } from '../lib/chat/limits'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { createConversationState } from './useConversations'
import type { ConversationDependencies } from './useConversations'
import { useChatStream } from './useChatStream'
import { NEW_CHAT_DRAFT, visiblePath } from '../lib/chat/types'
import type { ChatMessage, ChatRequest, ChatTransport, MessageRecords, ConversationTitleRequest } from '../lib/chat/types'
import { FALLBACK_TITLE, fallbackConversationTitle, TITLE_INPUT_LIMIT } from '../lib/chat/titles'
import { createConversationTitles } from './useConversationTitles'
import type { ChatModelId } from './useModelSelection'
import { useChatDrafts } from './useChatDrafts'
import { indexSiblingVariants, siblingVariants, variantLeaf } from '../lib/chat/branches'
import { CHAT_STORAGE_KEY, parseChatSnapshot } from '../lib/chat/persistence'
import type { ChatSnapshot } from '../lib/chat/persistence'
import { compareConversations, CONVERSATIONS_STORAGE_KEY, parseConversationSnapshot } from '../lib/chat/conversations'
import { useChatBackend } from './useChatBackend'
import { messageContext } from '../lib/chat/textReferences'
import type { ConversationMode } from '../lib/chat/conversations'
import type { ReasoningPreference } from '../lib/chat/reasoning'
import { supportsPreference } from '../lib/chat/reasoning'
import { CHAT_MODELS } from './useModelSelection'
import { useAppNotifications } from './useAppNotifications'
import { normalizeAppError } from '../lib/notifications/errors'
import { applyToolProjection } from '../lib/chat/toolEvents'
import type { ToolRunRecords } from '../lib/chat/toolEvents'

export function createChatState(transport: ChatTransport, dependencies: ConversationDependencies = {}, conversations = createConversationState(dependencies)) {
  const notifications = useAppNotifications()
  const toolRuns = ref<ToolRunRecords>({})
  if (transport.backend) transport.backend.onToolState = next => {
    toolRuns.value = applyToolProjection(toolRuns.value, next)
  }
  const messages = ref<MessageRecords>({})
  const stream = useChatStream(transport)
  const researchModes = ref<Record<string, boolean>>({})
  watch(conversations.activeId, (next, previous) => {
    if (previous !== null || !next || conversations.records.value[next]?.sidebarVisible !== false
      || Object.hasOwn(researchModes.value, next)) return
    researchModes.value = { ...Object.fromEntries(Object.entries(researchModes.value).filter(([key]) => key !== NEW_CHAT_DRAFT)), [next]: researchModes.value[NEW_CHAT_DRAFT] === true }
  }, { flush: 'sync' })
  const researchMode = computed({
    get: () => researchModes.value[conversations.activeId.value ?? NEW_CHAT_DRAFT] === true,
    set: value => { researchModes.value[conversations.activeId.value ?? NEW_CHAT_DRAFT] = value },
  })
  const id = dependencies.id ?? (() => globalThis.crypto.randomUUID())
  const now = dependencies.now ?? (() => new Date().toISOString())
  const pathBoundaries = ref<Record<string, string | null>>({})
  const variantSummaries = ref<Record<string, ApiSchemas['VariantSummary']>>({})
  function path(conversationId: string, leaf: string | null): ChatMessage[] {
    if (transport.backend && leaf && !messages.value[leaf]) return []
    return visiblePath(messages.value, conversationId, leaf, pathBoundaries.value[conversationId])
  }
  const visible = computed(() => conversations.active.value ? path(conversations.active.value.id, conversations.active.value.activeLeafMessageId) : [])
  const generatingConversationId = ref<string | null>(null)
  const drafts = useChatDrafts(conversations.activeId)
  const settingsBusy = ref(false)
  type SettingChange = { conversationMode?: ConversationMode, reasoningPreference?: ReasoningPreference | null }
  const settingErrors = ref<Record<string, string>>({})
  const settingsError = computed(() => settingErrors.value[conversations.activeId.value ?? ''] ?? null)
  const failedSettings = new Map<string, SettingChange>()
  async function setConversationSettings(change: SettingChange): Promise<boolean> {
    if (settingsBusy.value) return false
    const existingDraft = drafts.draft.value
    const conversation = conversations.active.value ?? conversations.create()
    if (!drafts.draft.value && existingDraft) drafts.draft.value = existingDraft
    settingsBusy.value = true
    settingErrors.value = Object.fromEntries(Object.entries(settingErrors.value).filter(([id]) => id !== conversation.id))
    try {
      if (transport.backend) {
        await transport.backend.ensure(conversation)
        await transport.backend.patch(conversation.id, change)
      }
      else Object.assign(conversation, change)
      failedSettings.delete(conversation.id)
      return true
    }
    catch (cause) {
      failedSettings.set(conversation.id, change)
      const context = { operation: 'settings' as const, conversationId: conversation.id, attemptId: id() }
      settingErrors.value[conversation.id] = normalizeAppError(cause, context).message
      notifications?.reportError(cause, context, { label: 'Erneut speichern', onClick: () => {
        const pending = failedSettings.get(conversation.id)
        if (!pending) return false
        conversations.select(conversation.id)
        return setConversationSettings(pending)
      } })
      return false
    }
    finally { settingsBusy.value = false }
  }
  const setConversationMode = (conversationMode: ConversationMode) => setConversationSettings({ conversationMode })
  const setReasoningPreference = (reasoningPreference: ReasoningPreference | null) => setConversationSettings({ reasoningPreference })
  const retryConversationSettings = () => {
    const change = failedSettings.get(conversations.activeId.value ?? '')
    return change ? setConversationSettings(change) : Promise.resolve(false)
  }
  function reasoningPreference(modelId: string, conversationId: string): ReasoningPreference | null {
    const preference = conversations.records.value[conversationId]?.reasoningPreference
    return preference && supportsPreference(CHAT_MODELS.find(model => model.id === modelId), preference) ? preference : null
  }
  function reconcileReasoningPreference(modelId: string): Promise<boolean> {
    const conversation = conversations.active.value
    if (!conversation?.reasoningPreference || reasoningPreference(modelId, conversation.id)) return Promise.resolve(true)
    return setReasoningPreference(null)
  }
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
    if (conversation) {
      conversation.activeLeafMessageId = message.id; conversation.updatedAt = message.createdAt
      if (role === 'user' && !transport.backend) conversation.sidebarVisible = true
    }
    return messages.value[message.id] ?? message
  }

  function generate(input: ChatMessage, modelId: ChatModelId, attempt = 1, titleRequest?: ConversationTitleRequest, research?: ChatRequest['research']): void {
    const history = path(input.conversationId, input.id).map(messageContext)
    const reply = append(input.conversationId, input.id, 'assistant', '')
    reply.modelId = modelId
    generatingConversationId.value = input.conversationId
    reply.generationId = id()
    reply.modelId = modelId
    void stream.start({ generationId: reply.generationId, conversationId: input.conversationId, inputMessageId: input.id, modelId, reasoningPreference: reasoningPreference(modelId, input.conversationId), messages: history, attempt, ...(research ? { research } : {}), input: { ...input }, assistantMessageId: reply.id, conversation: { ...conversations.records.value[input.conversationId]! } }, {
      research: (state, view, loadFailed) => {
        reply.researchLoadFailed = loadFailed === true
        reply.research = view ?? (!loadFailed && reply.research ? { ...reply.research, state } : { version: 1, mode: 'web', generationId: reply.generationId!, sourceGenerationId: reply.generationId!, state, inherited: false, modelResponseObserved: false, claimSupport: 'unverified', sources: [], citations: [] })
      },
      delta: text => { reply.content += text },
      replace: text => { reply.content = text },
      continuation: count => { reply.continuationCount = count },
      status: next => {
        reply.status = next
        if (next === 'failed' && transport.backend && !reply.content) drafts.records.value[input.conversationId] = input.content
        const conversation = conversations.records.value[input.conversationId]
        if (!transport.backend && next === 'completed' && messages.value[reply.id] === reply && conversation?.titleSource === 'fallback' && conversation.title === FALLBACK_TITLE) {
          const context = path(input.conversationId, reply.id).map(message => message.content).join('\n')
          conversation.title = fallbackConversationTitle(context)
        }
        if (next === 'completed' && titleRequest) void titles.generate(titleRequest)
      },
      failure: (code, message, diagnostics) => { reply.errorCode = code; reply.errorMessage = message; if (diagnostics) reply.errorDiagnostics = diagnostics },
    }).finally(() => { generatingConversationId.value = null })
  }

  function resume(messageId: string): void {
    const reply = messages.value[messageId]
    const input = reply?.parentMessageId ? messages.value[reply.parentMessageId] : undefined
    const conversation = reply ? conversations.records.value[reply.conversationId] : undefined
    if (!reply?.generationId || !input || !conversation || stream.busy.value) return
    generatingConversationId.value = conversation.id
    // Keep the saved partial response visible until a resume snapshot arrives.
    void stream.start({ generationId: reply.generationId, conversationId: conversation.id, inputMessageId: input.id, assistantMessageId: reply.id, input: { ...input }, conversation: { ...conversation }, modelId: reply.modelId ?? '', messages: [], attempt: 1, resume: true }, {
      research: (state, view, loadFailed) => {
        reply.researchLoadFailed = loadFailed === true
        reply.research = view ?? (!loadFailed && reply.research ? { ...reply.research, state } : { version: 1, mode: 'web', generationId: reply.generationId!, sourceGenerationId: reply.generationId!, state, inherited: false, modelResponseObserved: false, claimSupport: 'unverified', sources: [], citations: [] })
      },
      delta: text => { reply.content += text }, replace: text => { reply.content = text }, status: next => { reply.status = next },
      continuation: count => { reply.continuationCount = count },
      failure: (code, message, diagnostics) => { reply.errorCode = code; reply.errorMessage = message; if (diagnostics) reply.errorDiagnostics = diagnostics },
    }).finally(() => { generatingConversationId.value = null })
  }

  function send(text: string, modelId: ChatModelId, attachments: NonNullable<ChatMessage['attachments']> = [], research?: ChatRequest['research']): boolean {
    const content = text.trim()
    if (settingsBusy.value || settingsError.value || stream.busy.value || !content || content.length > CHAT_LIMITS.max_message_chars) return false
    const draftConversationId = conversations.activeId.value
    const searchSelected = researchMode.value
    const conversation = conversations.active.value ?? conversations.create()
    researchModes.value[conversation.id] = searchSelected
    const parent = visible.value.at(-1)
    if (parent?.role === 'user') return false
    const needsTitle = conversation.activeLeafMessageId === null && !conversation.titleGenerationAttempted && conversation.titleSource === 'fallback'
    if (needsTitle) {
      if (!transport.backend) conversation.title = fallbackConversationTitle(content)
      conversation.titleGenerationAttempted = true
    }
    const input = append(conversation.id, conversation.activeLeafMessageId, 'user', content)
    if (attachments.length) input.attachments = attachments
    generate(input, modelId, 1, needsTitle ? { conversationId: conversation.id, inputMessageId: input.id, modelId, firstMessage: Array.from(content).slice(0, TITLE_INPUT_LIMIT).join('') } : undefined, research)
    drafts.clear(draftConversationId)
    return true
  }

  function newChat(): void {
    // An upload/settings draft already has an identity. Reuse it when returning
    // from another chat so its persisted draft and attachment IDs stay reachable.
    const prepared = Object.values(conversations.records.value)
      .filter(c => c.sidebarVisible === false && c.archivedAt === null && c.activeLeafMessageId === null)
      .sort(compareConversations)[0]
    conversations.activeId.value = prepared?.id ?? null
  }
  function selectVariant(messageId: string): boolean {
    const message = Object.hasOwn(messages.value, messageId) ? messages.value[messageId] : undefined
    const conversation = conversations.active.value
    if (stream.busy.value || !message || !conversation || message.conversationId !== conversation.id) return false
    rememberBranch()
    conversation.activeLeafMessageId = variantLeaf(messages.value, preferredLeaves.value, messageId)
    return true
  }

  function regenerate(messageId: string, modelId: ChatModelId): boolean {
    if (settingsBusy.value || settingsError.value || stream.busy.value) return false
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
    if (settingsBusy.value || settingsError.value || stream.busy.value || !content || content.length > CHAT_LIMITS.max_message_chars || original?.role !== 'user' || original.conversationId !== conversations.activeId.value) return false
    rememberBranch()
    const input = append(original.conversationId, original.parentMessageId, 'user', content)
    input.editedFromMessageId = original.id
    if (original.attachments?.some(file => file.textReference)) input.attachments = original.attachments.filter(file => file.textReference)
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
    return !settingsBusy.value && !settingsError.value && !stream.busy.value && reply?.role === 'assistant'
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
    const history = path(reply.conversationId, reply.id).map(messageContext)
    const continuationCount = (source.continuationCount ?? 0) + 1
    if (transport.backend) {
      rememberBranch()
      reply = append(source.conversationId, source.parentMessageId, 'assistant', source.content)
      reply.modelId = modelId
    }
    reply.generationId = id()
    reply.continuationCount = continuationCount
    delete reply.errorCode
    delete reply.errorMessage
    delete reply.errorDiagnostics
    generatingConversationId.value = reply.conversationId
    void stream.start({ generationId: reply.generationId ?? id(), conversationId: reply.conversationId, inputMessageId: source.parentMessageId!, assistantMessageId: reply.id, modelId, reasoningPreference: reasoningPreference(modelId, reply.conversationId), messages: history, inheritedResearch: Boolean(source.research), attempt: 1, operation: 'continue', continuationCount, ...(transport.backend ? { sourceAssistantMessageId: source.id, input: { ...messages.value[source.parentMessageId!]! }, conversation: { ...conversations.records.value[source.conversationId]! } } : {}) }, {
      research: (state, view, loadFailed) => {
        reply.researchLoadFailed = loadFailed === true
        reply.research = view ?? (!loadFailed && reply.research ? { ...reply.research, state } : { version: 1, mode: 'web', generationId: reply.generationId!, sourceGenerationId: reply.generationId!, state, inherited: false, modelResponseObserved: false, claimSupport: 'unverified', sources: [], citations: [] })
      },
      delta: text => { reply.content += text },
      replace: text => { reply.content = text },
      continuation: count => { reply.continuationCount = count },
      status: next => { reply.status = next },
      failure: (code, message, diagnostics) => { reply.errorCode = code; reply.errorMessage = message; if (diagnostics) reply.errorDiagnostics = diagnostics },
    }).finally(() => { generatingConversationId.value = null })
    return true
  }
  function remove(conversationId: string): void | Promise<void> {
    titles.cancel(conversationId)
    if (generatingConversationId.value === conversationId) stream.stop()
    messages.value = Object.fromEntries(Object.entries(messages.value).filter(([, message]) => message.conversationId !== conversationId))
    toolRuns.value = Object.fromEntries(Object.entries(toolRuns.value).filter(([, run]) => run.conversationId !== conversationId))
    drafts.remove(conversationId)
    researchModes.value = Object.fromEntries(Object.entries(researchModes.value).filter(([id]) => id !== conversationId))
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
  return { researchMode, toolRuns, settingsBusy, settingsError, setConversationMode, setReasoningPreference, reconcileReasoningPreference, retryConversationSettings, conversations, messages, pathBoundaries, variantSummaries, variantSummary: (id: string) => variantSummaries.value[id], visible, stream, titles, generatingConversationId, drafts, preferredLeaves, send, retry, canContinue, continueResponse, newChat, remove, selectVariant, regenerate, edit, variants, snapshot, hydrate, resume }
}

export function useChat(transport: ChatTransport) {
  const state = createChatState(transport)
  if (transport.backend) {
    const persistence = useChatBackend(state, transport)
    return { ...state, ...persistence }
  }
  const storageWarning = ref<string | null>(null)
  const retryPersistence = ref<(() => void) | null>(null)
  const lastPersistenceError = ref<string | null>(null)
  const pendingSave = ref(false)
  const restoredDrafts = ref(0)
  const notifications = useAppNotifications()
  watch(storageWarning, value => {
    if (!value) return
    lastPersistenceError.value = value
    const code = value.startsWith('Chats wurden') ? 'STORAGE_CHANGED' : value.startsWith('Gespeicherte Chats') ? 'STORAGE_INVALID' : 'STORAGE_UNAVAILABLE'
    notifications?.reportError({ code }, { operation: 'storage', attemptId: code }, code === 'STORAGE_CHANGED' ? { label: 'Seite neu laden', onClick: () => window.location.reload() } : undefined)
  })
  let stopWatching: (() => void) | undefined
  let timer: ReturnType<typeof setTimeout> | undefined
  const persistenceAllowed = ref(true)
  function flush(): void {
    clearTimeout(timer)
    timer = undefined
    if (!persistenceAllowed.value) return
    try {
      const serialized = JSON.stringify(state.snapshot())
      if (serialized.length > MAX_SNAPSHOT_CHARS) throw new Error('Speichergrenze erreicht')
      window.localStorage.setItem(CHAT_STORAGE_KEY, serialized)
      pendingSave.value = false
      storageWarning.value = null; retryPersistence.value = null
    }
    catch { storageWarning.value = 'Änderungen können gerade nicht lokal gespeichert werden.'; retryPersistence.value = flush }
  }
  function externalChange(event: StorageEvent): void {
    if (event.key !== CHAT_STORAGE_KEY) return
    persistenceAllowed.value = false
    state.titles.dispose()
    storageWarning.value = 'Chats wurden in einem anderen Tab geändert. Lade diese Seite neu, um den aktuellen Stand zu verwenden.'
  }
  function pageHidden(): void { state.titles.cancelAll(); flush() }
  onMounted(() => {
    try {
      const raw = window.localStorage.getItem(CHAT_STORAGE_KEY)
      if (raw) {
        const saved = parseChatSnapshot(raw)
        if (saved) { state.hydrate(saved); restoredDrafts.value = Object.values(saved.drafts).filter(Boolean).length }
        else { persistenceAllowed.value = false; storageWarning.value = 'Gespeicherte Chats konnten nicht geladen werden. Der bisherige Speicher bleibt erhalten.' }
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
      pendingSave.value = true
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
  const persistenceStatus = computed<import('../lib/chat/persistence').PersistenceStatus>(() => ({
    storage: 'local', ready: !storageWarning.value && persistenceAllowed.value,
    blocked: !persistenceAllowed.value,
    recovery: storageWarning.value?.startsWith('Chats wurden') ? 'reload' : retryPersistence.value ? 'retry' : null,
    pendingOperations: Number(pendingSave.value),
    pendingDrafts: pendingSave.value ? Object.values(state.drafts.records.value).filter(Boolean).length : 0,
    failedOperations: Number(Boolean(storageWarning.value)), restoredDrafts: restoredDrafts.value,
    lastError: lastPersistenceError.value,
  }))
  return { ...state, storageWarning, retryPersistence, persistenceStatus, saveModelPreference: async (_modelId: string) => {}, pagination: undefined, backendReady: ref(true), importAvailable: ref(false), importBusy: ref(false), importLocalChats: async () => {} }
}
