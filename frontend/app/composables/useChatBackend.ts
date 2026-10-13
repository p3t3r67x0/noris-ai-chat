import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { createChatState } from './useChat'
import type { ChatTransport } from '../lib/chat/types'
import { conversationFromServer, messageFromServer } from '../lib/chat/backend'
import type { ApiSchemas } from '../types/generated/api'
import { ChatLoadCache } from '../lib/chat/loadCache'
import { CHAT_STORAGE_KEY, parseChatSnapshot } from '../lib/chat/persistence'
import { compareConversations } from '../lib/chat/conversations'
import { useAppNotifications } from './useAppNotifications'
import { normalizeAppError } from '../lib/notifications/errors'
import type { ErrorContext } from '../lib/notifications/errors'
import type { NotificationAction } from './useAppNotifications'
import { TransportError } from '../lib/chat/realTransport'

export const CHAT_CACHE_KEY = 'noris-ai:chat-cache:v2'
const OFFLINE_DRAFTS_KEY = 'noris-ai:offline-drafts:v1'

/** Synchronizes the existing state through explicit resource operations. */
export function useChatBackend(state: ReturnType<typeof createChatState>, transport: ChatTransport) {
  const notifications = useAppNotifications()
  function report(cause: unknown, context: ErrorContext, action?: NotificationAction): string {
    notifications?.reportError(cause, context, action)
    return normalizeAppError(cause, context).message
  }
  const backend = transport.backend!
  backend.onMessage = (value) => {
    const existing = state.messages.value[value.id]
    if (existing) existing.attachments = value.attachments ?? []
  }
  const storageWarning = ref<string | null>(null)
  const retryPersistence = ref<(() => Promise<void> | void) | null>(null)
  const failedPersistence = new Map<string, { message: string, retry: () => Promise<void> }>()
  const failedDrafts = new Map<string, string>()
  function syncPersistenceRecovery(): void {
    storageWarning.value = [...failedPersistence.values()].at(-1)?.message ?? null
    retryPersistence.value = failedPersistence.size ? async () => { for (const failure of [...failedPersistence.values()]) await failure.retry() } : null
  }
  const backendReady = ref(false)
  const importAvailable = ref(false)
  const importBusy = ref(false)
  let disposed = false
  let userNavigated = false
  const sidebarIds = ref<string[]>([])
  const sidebarLoading = ref(false)
  const sidebarError = ref<string | null>(null)
  const nextCursor = ref<string | null>(null)
  const historyLoading = ref(false)
  const historyError = ref<string | null>(null)
  const windows = ref<Record<string, ApiSchemas['ActivePathResponse']>>({})
  const cache = new ChatLoadCache()
  let viewRequest: { id: string, abort: AbortController } | undefined
  let viewRevision = 0
  let selectingVariant: string | undefined
  let olderConversation: string | undefined
  const olderLoading = ref(false)
  let timer: ReturnType<typeof setTimeout> | undefined
  let draftTimer: ReturnType<typeof setTimeout> | undefined
  let sentDrafts: Record<string, string> = {}
  let pendingDrafts: Record<string, string> = {}
  let preferredModelId: string | null = null
  function localJson(key: string, maximum = Infinity): unknown {
    try {
      const raw = localStorage.getItem(key)
      return raw && raw.length <= maximum ? JSON.parse(raw) : null
    }
    catch { return null }
  }
  function savePendingDrafts(): void {
    try {
      localStorage.setItem(OFFLINE_DRAFTS_KEY, JSON.stringify(pendingDrafts))
      if (retryPersistence.value === savePendingDrafts) syncPersistenceRecovery()
    }
    catch { storageWarning.value = report({ code: 'STORAGE_UNAVAILABLE' }, { operation: 'storage', resourceId: 'drafts' }); retryPersistence.value = savePendingDrafts }
  }

  function mergeMetadata(values: ApiSchemas['ConversationResponse'][]): void {
    for (const value of values) {
      const existingVersion = backend.versions.get(value.id) ?? 0
      if (value.version < existingVersion) continue
      backend.versions.set(value.id, value.version)
      // Replace the rendered record so every consumer sees this server revision.
      state.conversations.records.value[value.id] = conversationFromServer(value)
    }
    const pinned = new Set([...sidebarIds.value, ...Object.keys(windows.value), ...values.map(c => c.id), ...Object.keys(pendingDrafts), state.conversations.activeId.value, state.generatingConversationId.value])
    const records = Object.entries(state.conversations.records.value)
    const remove = new Set(records.filter(([id]) => !pinned.has(id)).slice(0, Math.max(0, records.length - 600)).map(([id]) => id))
    if (remove.size) {
      state.conversations.records.value = Object.fromEntries(records.filter(([id]) => !remove.has(id)))
      for (const id of remove) { backend.versions.delete(id); cache.invalidate(id) }
    }
  }
  function evict(): void {
    const pinned = new Set([state.conversations.activeId.value, state.generatingConversationId.value, olderConversation, ...cache.pendingIds(), ...Object.keys(pendingDrafts)].filter((id): id is string => Boolean(id)))
    const ids = new Set(cache.evictions(pinned))
    // Additional byte budget bounds unusually large inactive responses.
    let bytes = Object.values(state.messages.value).reduce((total, m) => total + m.content.length * 2 + 512, 0)
    for (const id of Object.keys(windows.value)) {
      if (bytes <= 8 * 1024 * 1024) break
      if (pinned.has(id)) continue
      ids.add(id)
      bytes -= Object.values(state.messages.value).filter(m => m.conversationId === id).reduce((total, m) => total + m.content.length * 2 + 512, 0)
    }
    if (ids.size) {
      state.messages.value = Object.fromEntries(Object.entries(state.messages.value).filter(([, m]) => !ids.has(m.conversationId)))
      windows.value = Object.fromEntries(Object.entries(windows.value).filter(([id]) => !ids.has(id)))
      state.pathBoundaries.value = Object.fromEntries(Object.entries(state.pathBoundaries.value).filter(([id]) => !ids.has(id)))
      sentDrafts = Object.fromEntries(Object.entries(sentDrafts).filter(([id]) => !ids.has(id)))
      state.drafts.records.value = Object.fromEntries(Object.entries(state.drafts.records.value).filter(([id]) => !ids.has(id)))
      for (const id of ids) cache.invalidate(id)
      state.variantSummaries.value = Object.fromEntries(Object.entries(state.variantSummaries.value).filter(([id]) => Boolean(state.messages.value[id])))
    }
  }
  function applyPath(result: ApiSchemas['ActivePathResponse'], append = false): void {
    const previousMessages = state.messages.value
    const id = result.conversation.id
    const retainsBoundary = append && result.boundaryParentId && state.messages.value[result.boundaryParentId]?.conversationId === id
    if (!append) {
      state.messages.value = Object.fromEntries(Object.entries(state.messages.value).filter(([, m]) => m.conversationId !== id))
      state.variantSummaries.value = Object.fromEntries(Object.entries(state.variantSummaries.value).filter(([key]) => Boolean(state.messages.value[key])))
    }
    for (const message of result.messages) {
      const existing = previousMessages[message.id]
      const loaded = messageFromServer(message)
      if (existing?.errorDiagnostics && existing.generationId === loaded.generationId && existing.errorCode === loaded.errorCode) loaded.errorDiagnostics = existing.errorDiagnostics
      state.messages.value[message.id] = loaded
    }
    for (const summary of result.variants) state.variantSummaries.value[summary.messageId] = summary
    if (!retainsBoundary) state.pathBoundaries.value[id] = result.boundaryParentId ?? null
    windows.value[id] = retainsBoundary && windows.value[id]
      ? { ...result, nextCursor: windows.value[id].nextCursor ?? null, hasMore: windows.value[id].hasMore ?? false }
      : result
    mergeMetadata([result.conversation])
    cache.touch(id, result.conversation.version)
    evict()
  }
  async function loadConversation(id: string, force = false, preserve = false): Promise<void> {
    if (id === state.generatingConversationId.value) return
    if (!force && cache.valid(id, backend.versions.get(id) ?? 0)) return
    const foreground = state.conversations.activeId.value === id
    if (foreground && viewRequest && viewRequest.id !== id) { viewRequest.abort.abort(); cache.cancelRead(viewRequest.id) }
    const revision = foreground ? ++viewRevision : -1
    const controller = foreground && viewRequest?.id === id ? viewRequest.abort : new AbortController()
    if (foreground) { viewRequest = { id, abort: controller }; historyLoading.value = true; historyError.value = null }
    try {
      const conversation = state.conversations.records.value[id]
      // A file selection can create a chat before its first message. Wait for
      // that chat's existing persistence queue before requesting its empty path.
      if (conversation && !backend.versions.has(id)) await backend.ensure(conversation)
      if (disposed || controller.signal.aborted || id === state.generatingConversationId.value) return
      await cache.read(id, async () => {
        const [result, drafts] = await Promise.all([
          backend.path(id, {}, controller.signal),
          backend.request<ApiSchemas['DraftListResponse']>(`/chat/drafts?keys=${id}`, 'GET', undefined, controller.signal),
        ])
        if (disposed || controller.signal.aborted || !state.conversations.records.value[id]) return
        // A stream may have started while the request was pending.
        if (id === state.generatingConversationId.value) return
        if (result.conversation.version < (backend.versions.get(id) ?? 0) && result.leafMessageId !== state.conversations.records.value[id]?.activeLeafMessageId) throw new TransportError('VERSION_CONFLICT')
        applyPath(result, preserve)
        if (!Object.hasOwn(pendingDrafts, id)) {
          const content = drafts.drafts.find(draft => draft.key === id)?.content ?? ''
          sentDrafts[id] = content; state.drafts.records.value[id] = content
        }
        const running = result.messages.find(m => m.generationId && ['pending', 'streaming'].includes(m.status))
        if (running && !state.stream.busy.value) state.resume(running.id)
      })
    }
    catch (error) {
      if (!controller.signal.aborted && state.conversations.activeId.value === id) historyError.value = report(error, { operation: 'history', conversationId: id, attemptId: String(revision) }, { label: 'Chat erneut laden', onClick: () => loadConversation(id, true) })
    }
    finally { if (foreground && revision === viewRevision) { historyLoading.value = false; viewRequest = undefined } }
  }
  backend.onConversation = (value) => {
    const previous = state.conversations.records.value[value.id]
    // An active chat outside page one can become recent through a live update.
    // Its metadata then belongs in the sorted sidebar without reloading messages.
    if (value.version < (backend.versions.get(value.id) ?? 0)) return
    if (!value.archivedAt && value.sidebarVisible !== false && (!previous || previous.sidebarVisible === false || compareConversations(conversationFromServer(value), previous) < 0) && !sidebarIds.value.includes(value.id)) {
      sidebarIds.value = [value.id, ...sidebarIds.value].slice(0, 500)
    }
    const changedLeaf = previous?.activeLeafMessageId !== value.activeLeafMessageId
    if (changedLeaf && value.id === state.conversations.activeId.value && value.id !== state.generatingConversationId.value) {
      // Retain the displayed path until its new authoritative window is ready.
      mergeMetadata([{ ...value, activeLeafMessageId: previous?.activeLeafMessageId ?? null }])
      cache.invalidate(value.id)
      if (selectingVariant !== value.id) void loadConversation(value.id, true)
      return
    }
    mergeMetadata([value])
    if (!changedLeaf && windows.value[value.id]) cache.touch(value.id, value.version)
    if (changedLeaf && value.id === state.conversations.activeId.value && !state.messages.value[value.activeLeafMessageId ?? ''] && value.id !== state.generatingConversationId.value) void loadConversation(value.id, true)
  }
  backend.onMetadata = (values, activeId) => {
    if (disposed) return
    mergeMetadata(values)
    sidebarIds.value = backend.initialPage?.conversations.map(c => c.id) ?? []
    if (!userNavigated) state.conversations.activeId.value = activeId
  }
  async function refresh(): Promise<void> {
    const snapshot = await backend.load()
    if (disposed) return
    // Metadata arrives before the active path; never hydrate a partial tree as a legacy snapshot.
    mergeMetadata(snapshot.metadata)
    sentDrafts = { ...sentDrafts, ...snapshot.drafts }
    state.drafts.records.value = { ...state.drafts.records.value, ...snapshot.drafts, ...pendingDrafts }
    sidebarIds.value = backend.initialPage?.conversations.map(c => c.id) ?? []
    nextCursor.value = backend.initialPage?.nextCursor ?? null
    if (backend.initialPath) applyPath(backend.initialPath)
    backendReady.value = true
    const active = state.conversations.activeId.value
    if (active && active !== backend.initialPath?.conversation.id) void loadConversation(active)
  }
  async function loadMore(): Promise<void> {
    if (sidebarLoading.value || !nextCursor.value) return
    sidebarLoading.value = true; sidebarError.value = null
    try {
      const result = await backend.page({ cursor: nextCursor.value })
      if (disposed) return
      mergeMetadata(result.conversations); nextCursor.value = result.nextCursor ?? null
      sidebarIds.value = [...new Set([...sidebarIds.value, ...result.conversations.map(c => c.id)])].slice(-500)
    }
    catch (error) { sidebarError.value = report(error, { operation: 'sidebar', resourceId: 'more', attemptId: crypto.randomUUID() }, { label: 'Erneut laden', onClick: loadMore }) }
    finally { sidebarLoading.value = false }
  }
  async function reloadSidebar(): Promise<void> {
    if (sidebarLoading.value) return
    const previousError = sidebarError.value
    sidebarLoading.value = true; sidebarError.value = null
    try {
      if (!backendReady.value) await refresh()
      else {
        const result = await backend.page()
        if (disposed) return
        mergeMetadata(result.conversations)
        sidebarIds.value = result.conversations.map(c => c.id)
        nextCursor.value = result.nextCursor ?? null
      }
      await transport.connect?.()
      if (storageWarning.value === previousError) storageWarning.value = null
    }
    catch (error) { sidebarError.value = report(error, { operation: 'sidebar', attemptId: crypto.randomUUID() }, { label: 'Erneut laden', onClick: reloadSidebar }) }
    finally { sidebarLoading.value = false }
  }
  async function loadOlder(): Promise<void> {
    const id = state.conversations.activeId.value
    const cursor = id ? windows.value[id]?.nextCursor : null
    const boundary = id ? state.pathBoundaries.value[id] : null
    if (!id || !cursor || !boundary || olderLoading.value || state.stream.busy.value) return
    olderLoading.value = true; historyError.value = null
    olderConversation = id
    try {
      const result = await backend.path(id, { beforeMessageId: boundary })
      if (!disposed && state.conversations.records.value[id] && result.leafMessageId === state.conversations.records.value[id]?.activeLeafMessageId) applyPath(result, true)
    }
    catch (error) { if (state.conversations.activeId.value === id) historyError.value = report(error, { operation: 'older-history', conversationId: id, attemptId: crypto.randomUUID() }, { label: 'Erneut laden', onClick: loadOlder }) }
    finally { olderLoading.value = false; olderConversation = undefined }
  }
  async function search(query: string, signal: AbortSignal, cursor?: string): Promise<ApiSchemas['ConversationListResponse']> {
    const result = await backend.page({ q: query, ...(cursor ? { cursor } : {}) }, signal)
    if (!disposed && !signal.aborted) mergeMetadata(result.conversations)
    return result
  }
  async function loadArchive(cursor?: string): Promise<ApiSchemas['ConversationListResponse']> {
    const result = await backend.page({ archiveOnly: 'true', ...(cursor ? { cursor } : {}) })
    if (!disposed) mergeMetadata(result.conversations)
    return result
  }
  async function persist(operation: Promise<unknown>, context: ErrorContext, retry: () => Promise<unknown>): Promise<void> {
    const key = JSON.stringify([context.operation, context.conversationId, context.resourceId])
    try { await operation; if (failedPersistence.delete(key)) syncPersistenceRecovery() }
    catch (error) {
      const recover = () => persist(retry(), { ...context, attemptId: crypto.randomUUID() }, retry)
      const message = report(error, context, { label: 'Erneut speichern', onClick: recover })
      failedPersistence.set(key, { message, retry: recover }); syncPersistenceRecovery()
      // On conflict, re-read authority. Preserve the unsent draft for recovery.
      if (!state.stream.busy.value) {
        const drafts = { ...state.drafts.records.value }
        try { await refresh(); state.drafts.records.value = { ...state.drafts.records.value, ...drafts } }
        catch { backendReady.value = false }
      }
    }
  }
  const create = state.conversations.create
  const select = state.conversations.select
  state.conversations.select = (id) => { userNavigated = true; select(id) }
  state.conversations.create = (title?: string) => {
    userNavigated = true
    const conversation = create(title)
    void persist(backend.ensure(conversation), { operation: 'create', conversationId: conversation.id, attemptId: crypto.randomUUID() }, () => backend.ensure(conversation))
    return conversation
  }
  const newChat = state.newChat
  state.newChat = () => { userNavigated = true; newChat() }
  for (const action of ['rename', 'archive', 'restore'] as const) {
    const original = state.conversations[action]
    state.conversations[action] = (id: string, title?: string) => {
      if (!backendReady.value) return
      original(id, title ?? '')
      if (action === 'restore') sidebarIds.value = [id, ...sidebarIds.value.filter(value => value !== id)].slice(0, 500)
      const change = action === 'rename' ? { title: title ?? '' } : { archived: action === 'archive' }
      const operation = action === 'archive' ? 'archive' : action
      void persist(backend.patch(id, change), { operation, conversationId: id, attemptId: crypto.randomUUID() }, () => backend.patch(id, change))
    }
  }
  state.selectVariant = (id) => {
    const conversation = state.conversations.active.value
    if (!backendReady.value || state.stream.busy.value || !conversation || historyLoading.value) return false
    const conversationId = conversation.id
    const revision = ++viewRevision
    const controller = new AbortController()
    viewRequest = { id: conversationId, abort: controller }
    selectingVariant = conversationId
    const leaf = conversation.activeLeafMessageId
    if (leaf) for (const message of state.visible.value) state.preferredLeaves.value[message.id] = leaf
    historyLoading.value = true
    void (async () => {
      try {
        const result = await backend.path(conversationId, { messageId: id, ...(state.preferredLeaves.value[id] ? { preferredLeafId: state.preferredLeaves.value[id] } : {}) }, controller.signal)
        if (disposed || state.conversations.activeId.value !== conversationId || state.stream.busy.value) return
        if (!result.leafMessageId) return
        // Persist selection before presenting the resolved path.
        await backend.patch(conversationId, { activeLeafMessageId: result.leafMessageId })
        // The PATCH may have observed a title committed after this path was read.
        // Preserve that metadata when presenting the selected message window.
        result.conversation = { ...result.conversation, ...state.conversations.records.value[conversationId], activeLeafMessageId: result.leafMessageId, version: backend.versions.get(conversationId)! }
        applyPath(result)
      }
      catch (error) { if (!controller.signal.aborted && state.conversations.activeId.value === conversationId) historyError.value = report(error, { operation: 'variant', conversationId, resourceId: id, attemptId: String(revision) }, { label: 'Chat erneut laden', onClick: () => loadConversation(conversationId, true) }) }
      finally { if (revision === viewRevision) { historyLoading.value = false; viewRequest = undefined }; if (selectingVariant === conversationId) selectingVariant = undefined }
    })()
    return true
  }
  const regenerate = state.regenerate
  state.regenerate = (id, modelId) => {
    if (historyLoading.value || historyError.value) return false
    const message = state.messages.value[id]
    if (message?.role === 'assistant' && message.parentMessageId && !state.messages.value[message.parentMessageId]) {
      const conversationId = message.conversationId
      void loadOlder().then(() => { if (state.conversations.activeId.value === conversationId) regenerate(id, modelId) })
      return true
    }
    return regenerate(id, modelId)
  }
  const remove = state.remove
  state.remove = async (id) => {
    if (!backendReady.value) throw new TransportError('NOT_READY')
    // Confirm the existing server deletion before discarding messages and drafts.
    // The confirmation dialog owns the error and remains available for retry.
    await backend.remove(id)
    cache.invalidate(id)
    windows.value = Object.fromEntries(Object.entries(windows.value).filter(([key]) => key !== id))
    state.pathBoundaries.value = Object.fromEntries(Object.entries(state.pathBoundaries.value).filter(([key]) => key !== id))
    remove(id)
  }
  function flushCache(): void {
    try {
      localStorage.setItem(CHAT_CACHE_KEY, JSON.stringify({ version: 2, preferredLeaves: state.preferredLeaves.value }))
      if (retryPersistence.value === flushCache) syncPersistenceRecovery()
    }
    catch { storageWarning.value = report({ code: 'STORAGE_UNAVAILABLE' }, { operation: 'storage', resourceId: 'cache' }); retryPersistence.value = flushCache }
  }
  async function importLocalChats(): Promise<void> {
    if (importBusy.value || !backendReady.value) return
    importBusy.value = true
    try {
      const raw = localStorage.getItem(CHAT_STORAGE_KEY)
      const snapshot = raw ? parseChatSnapshot(raw) : null
      if (!snapshot) throw new TransportError('IMPORT_INVALID')
      const result = await backend.request<{ conflicts: unknown[], imported: string[], skipped: string[] }>('/conversations/import', 'POST', {
        conversations: Object.values(snapshot.conversations.conversations).map(({ titleGenerationAttempted: _attempted, ...c }) => c),
        messages: Object.values(snapshot.messages).map(m => ({ id: m.id, conversationId: m.conversationId, parentMessageId: m.parentMessageId, role: m.role, content: m.content, modelId: m.modelId ?? null, continuationCount: m.continuationCount ?? 0, errorCode: m.errorCode ?? null, errorMessage: m.errorMessage ?? null, editedFromMessageId: m.editedFromMessageId ?? null, status: m.status === 'submitting' || m.status === 'streaming' ? 'cancelled' : m.status, createdAt: m.createdAt, updatedAt: m.createdAt })),
        drafts: snapshot.drafts, activeConversationId: snapshot.conversations.activeConversationId,
      })
      if (result.conflicts.length) throw new TransportError('IMPORT_CONFLICT')
      await refresh()
      storageWarning.value = `${result.imported.length} Chats importiert, ${result.skipped.length} bereits vorhanden. Die lokale Sicherung bleibt erhalten.`
      notifications?.notify({ severity: 'success', title: 'Chats importiert.', description: storageWarning.value })
    }
    catch (error) { storageWarning.value = report(error, { operation: 'import', attemptId: crypto.randomUUID() }, { label: 'Erneut importieren', onClick: importLocalChats }) }
    finally { importBusy.value = false }
  }
  onMounted(async () => {
    sidebarLoading.value = true
    try {
      try { importAvailable.value = Boolean(localStorage.getItem(CHAT_STORAGE_KEY)) }
      catch { storageWarning.value = report({ code: 'STORAGE_UNAVAILABLE' }, { operation: 'storage', resourceId: 'import' }) }
      const offline = localJson(OFFLINE_DRAFTS_KEY)
      if (offline && typeof offline === 'object' && !Array.isArray(offline)) {
        for (const [key, text] of Object.entries(offline)) if (typeof text === 'string' && text.length <= 64000 && (key === '__new__' || /^[0-9a-f-]{36}$/.test(key))) {
          pendingDrafts[key] = text
          state.drafts.records.value[key] = text
        }
        if (Object.keys(pendingDrafts).length) {
          storageWarning.value = 'Ein lokal noch nicht gespeicherter Entwurf wurde wiederhergestellt.'
          notifications?.notify({ severity: 'info', title: 'Entwurf wiederhergestellt.', description: storageWarning.value })
        }
      }
      await refresh()
      // Recover an explicitly saved reader position with bounded active-chat
      // paging. No inactive messages are loaded. At most 20 pages (1,000 rows).
      const positions = localJson('noris-ai:chat-scroll:v1', 16000)
      if (positions) {
        const active = state.conversations.activeId.value
        const entry = Array.isArray(positions) ? positions.find(item => Array.isArray(item) && item[0] === active) : undefined
        const anchor = entry?.[1]?.following === false && typeof entry[1].messageId === 'string' ? entry[1].messageId : null
        for (let page = 0; anchor && !state.messages.value[anchor] && windows.value[active ?? '']?.nextCursor && page < 20; page++) {
          await loadOlder()
          if (historyError.value) break
        }
      }
      await transport.connect?.()
      // Only variant-view preferences are read from cache. Message content and
      // active conversation always come from the database.
      const value = localJson(CHAT_CACHE_KEY, 256000)
      if (value) {
        if (value && typeof value === 'object' && 'preferredLeaves' in value && value.preferredLeaves && typeof value.preferredLeaves === 'object') {
          state.preferredLeaves.value = Object.fromEntries(Object.entries(value.preferredLeaves).filter(([node, leaf]) => /^[0-9a-f-]{36}$/.test(node) && typeof leaf === 'string' && /^[0-9a-f-]{36}$/.test(leaf)).slice(-2000))
        }
      }
      const running = Object.values(state.messages.value).find(m => m.generationId && (m.status === 'streaming' || m.status === 'submitting'))
      if (running) state.resume(running.id)
    }
    catch (error) { storageWarning.value = report(error, { operation: 'sidebar', attemptId: 'initial' }, { label: 'Erneut laden', onClick: reloadSidebar }); sidebarError.value = storageWarning.value }
    finally { sidebarLoading.value = false }
  })
  watch([state.preferredLeaves, state.conversations.activeId], () => {
    clearTimeout(timer); timer = setTimeout(flushCache, 120)
  }, { deep: true })
  watch(state.conversations.activeId, id => {
    if (backendReady.value) {
      if (viewRequest && viewRequest.id !== id) { viewRequest.abort.abort(); cache.cancelRead(viewRequest.id); viewRequest = undefined }
      ++viewRevision; historyLoading.value = false
      void persist(backend.preferences(id), { operation: 'preferences', conversationId: id, attemptId: crypto.randomUUID() }, () => backend.preferences(state.conversations.activeId.value))
      historyError.value = null
      if (id) void loadConversation(id)
      else { historyLoading.value = false; viewRequest?.abort.abort() }
    }
  })
  watch(state.generatingConversationId, (id, previous) => {
    if (!id && previous) { cache.invalidate(previous); void loadConversation(previous, true, true); evict() }
  })
  watch(state.drafts.records, () => {
    let changed = false
    for (const [key, content] of Object.entries(state.drafts.records.value)) if (sentDrafts[key] !== content && pendingDrafts[key] !== content) {
      pendingDrafts[key] = content; changed = true
    }
    if (changed) savePendingDrafts()
    clearTimeout(draftTimer)
    draftTimer = setTimeout(() => {
      if (!backendReady.value) return
      for (const [key, content] of Object.entries(state.drafts.records.value)) {
        if (sentDrafts[key] === content || (key !== '__new__' && !state.conversations.records.value[key])) continue
        if (failedDrafts.get(key) === content) continue
        const saveDraft = async () => {
          if (key !== '__new__' && !state.conversations.records.value[key]) return
          const currentContent = state.drafts.records.value[key] ?? content
          try { await backend.draft(key, currentContent) }
          catch (cause) { failedDrafts.set(key, currentContent); throw cause }
          failedDrafts.delete(key)
          sentDrafts[key] = currentContent
          if (pendingDrafts[key] === currentContent) pendingDrafts = Object.fromEntries(Object.entries(pendingDrafts).filter(([id]) => id !== key))
          savePendingDrafts()
        }
        void persist(saveDraft(), { operation: 'draft', conversationId: key, attemptId: crypto.randomUUID() }, saveDraft)
      }
      flushCache()
    }, 300)
  }, { deep: true, flush: 'sync' })
  onUnmounted(() => { disposed = true; viewRequest?.abort.abort(); clearTimeout(timer); clearTimeout(draftTimer); flushCache(); transport.dispose?.() })
  const pagination = {
    conversations: computed(() => sidebarIds.value.flatMap(id => { const c = state.conversations.records.value[id]; return c && !c.archivedAt && c.sidebarVisible !== false ? [c] : [] })),
    sidebarLoading, sidebarError, hasMore: computed(() => Boolean(nextCursor.value)), loadMore, reloadSidebar,
    windowedList: computed(() => sidebarIds.value.length >= 500),
    historyLoading, historyError, olderLoading,
    hasOlder: computed(() => Boolean(windows.value[state.conversations.activeId.value ?? '']?.nextCursor)),
    loadOlder, retryHistory: () => { const id = state.conversations.activeId.value; if (id) void loadConversation(id, true) },
    search, loadArchive, loadConversation,
  }
  function saveModelPreference(modelId: string): Promise<void> {
    preferredModelId = modelId
    return persist(backend.preferences(state.conversations.activeId.value, modelId), { operation: 'preferences', resourceId: 'model', attemptId: crypto.randomUUID() }, () => backend.preferences(state.conversations.activeId.value, preferredModelId ?? modelId))
  }
  return { pagination, storageWarning, retryPersistence, saveModelPreference, backendReady, importAvailable, importBusy, importLocalChats, refresh }
}
