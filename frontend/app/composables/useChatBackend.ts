import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { createChatState } from './useChat'
import type { ChatTransport } from '../lib/chat/types'
import { conversationFromServer, messageFromServer } from '../lib/chat/backend'
import type { ApiSchemas } from '../types/generated/api'
import { ChatLoadCache } from '../lib/chat/loadCache'
import { CHAT_STORAGE_KEY, parseChatSnapshot } from '../lib/chat/persistence'

export const CHAT_CACHE_KEY = 'noris-ai:chat-cache:v2'
const OFFLINE_DRAFTS_KEY = 'noris-ai:offline-drafts:v1'

/** Synchronizes the existing state through explicit resource operations. */
export function useChatBackend(state: ReturnType<typeof createChatState>, transport: ChatTransport) {
  const backend = transport.backend!
  const storageWarning = ref<string | null>(null)
  const backendReady = ref(false)
  const importAvailable = ref(false)
  const importBusy = ref(false)
  let disposed = false
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
  const olderLoading = ref(false)
  let timer: ReturnType<typeof setTimeout> | undefined
  let draftTimer: ReturnType<typeof setTimeout> | undefined
  let sentDrafts: Record<string, string> = {}
  let pendingDrafts: Record<string, string> = {}
  function savePendingDrafts(): void {
    try { localStorage.setItem(OFFLINE_DRAFTS_KEY, JSON.stringify(pendingDrafts)) }
    catch { storageWarning.value = 'Der lokale Entwurf konnte nicht gesichert werden.' }
  }

  function mergeMetadata(values: ApiSchemas['ConversationResponse'][]): void {
    for (const value of values) {
      const existingVersion = backend.versions.get(value.id) ?? 0
      if (value.version < existingVersion) continue
      backend.versions.set(value.id, value.version)
      const existing = state.conversations.records.value[value.id]
      if (existing) Object.assign(existing, conversationFromServer(value))
      else state.conversations.records.value[value.id] = conversationFromServer(value)
    }
  }
  function evict(): void {
    const pinned = new Set([state.conversations.activeId.value, state.generatingConversationId.value, ...Object.keys(pendingDrafts)].filter((id): id is string => Boolean(id)))
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
      for (const id of ids) cache.invalidate(id)
      state.variantSummaries.value = Object.fromEntries(Object.entries(state.variantSummaries.value).filter(([id]) => Boolean(state.messages.value[id])))
    }
  }
  function applyPath(result: ApiSchemas['ActivePathResponse'], append = false): void {
    const id = result.conversation.id
    if (!append) state.messages.value = Object.fromEntries(Object.entries(state.messages.value).filter(([, m]) => m.conversationId !== id))
    for (const message of result.messages) state.messages.value[message.id] = messageFromServer(message)
    for (const summary of result.variants) state.variantSummaries.value[summary.messageId] = summary
    state.pathBoundaries.value[id] = result.boundaryParentId ?? null
    windows.value[id] = result
    mergeMetadata([result.conversation])
    cache.touch(id, result.conversation.version)
    evict()
  }
  async function loadConversation(id: string, force = false): Promise<void> {
    if (id === state.generatingConversationId.value) return
    if (!force && cache.valid(id, backend.versions.get(id) ?? 0)) return
    if (viewRequest && viewRequest.id !== id) { viewRequest.abort.abort(); cache.cancelRead(viewRequest.id) }
    const revision = ++viewRevision
    const controller = viewRequest?.id === id ? viewRequest.abort : new AbortController()
    viewRequest = { id, abort: controller }
    if (state.conversations.activeId.value === id) { historyLoading.value = true; historyError.value = null }
    try {
      await cache.read(id, async () => {
        const [result, drafts] = await Promise.all([
          backend.path(id, {}, controller.signal),
          backend.request<ApiSchemas['DraftListResponse']>(`/chat/drafts?keys=${id}`, 'GET', undefined, controller.signal),
        ])
        if (disposed || controller.signal.aborted || !state.conversations.records.value[id]) return
        // A stream may have started while the request was pending.
        if (id === state.generatingConversationId.value) return
        if (result.conversation.version < (backend.versions.get(id) ?? 0) && result.leafMessageId !== state.conversations.records.value[id]?.activeLeafMessageId) throw new Error('Der Gesprächspfad wurde geändert. Lade den Chat erneut.')
        applyPath(result)
        for (const draft of drafts.drafts) if (!Object.hasOwn(pendingDrafts, draft.key)) {
          sentDrafts[draft.key] = draft.content; state.drafts.records.value[draft.key] = draft.content
        }
        const running = result.messages.find(m => m.generationId && ['pending', 'streaming'].includes(m.status))
        if (running && !state.stream.busy.value) state.resume(running.id)
      })
    }
    catch (error) {
      if (!controller.signal.aborted && state.conversations.activeId.value === id) historyError.value = error instanceof Error ? error.message : 'Dieser Chat konnte nicht geladen werden.'
    }
    finally { if (revision === viewRevision) { historyLoading.value = false; viewRequest = undefined } }
  }
  backend.onConversation = (value) => {
    const previous = state.conversations.records.value[value.id]
    const changedLeaf = previous?.activeLeafMessageId !== value.activeLeafMessageId
    mergeMetadata([value])
    if (!changedLeaf && windows.value[value.id]) cache.touch(value.id, value.version)
    if (changedLeaf && value.id === state.conversations.activeId.value && !state.messages.value[value.activeLeafMessageId ?? ''] && value.id !== state.generatingConversationId.value) void loadConversation(value.id, true)
  }
  backend.onMetadata = (values, activeId) => {
    if (disposed) return
    mergeMetadata(values)
    state.conversations.activeId.value = activeId
  }
  async function refresh(): Promise<void> {
    const snapshot = await backend.load()
    if (disposed) return
    // Metadata arrives before the active path; never hydrate a partial tree as a legacy snapshot.
    mergeMetadata(Object.values(snapshot.conversations.conversations).map(c => ({ ...c, version: backend.versions.get(c.id) ?? 1, lastMessageAt: null })))
    state.drafts.records.value = { ...snapshot.drafts, ...pendingDrafts }
    sentDrafts = { ...snapshot.drafts }
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
    catch (error) { sidebarError.value = error instanceof Error ? error.message : 'Weitere Chats konnten nicht geladen werden.' }
    finally { sidebarLoading.value = false }
  }
  async function loadOlder(): Promise<void> {
    const id = state.conversations.activeId.value
    const cursor = id ? windows.value[id]?.nextCursor : null
    if (!id || !cursor || olderLoading.value || state.stream.busy.value) return
    olderLoading.value = true; historyError.value = null
    try {
      const result = await backend.path(id, { cursor })
      if (!disposed && state.conversations.records.value[id] && result.leafMessageId === state.conversations.records.value[id]?.activeLeafMessageId) applyPath(result, true)
    }
    catch (error) { historyError.value = error instanceof Error ? error.message : 'Ältere Nachrichten konnten nicht geladen werden.' }
    finally { olderLoading.value = false }
  }
  async function search(query: string, signal: AbortSignal): Promise<ApiSchemas['ConversationListResponse']> {
    const result = await backend.page({ q: query }, signal)
    if (!disposed) mergeMetadata(result.conversations)
    return result
  }
  async function loadArchive(cursor?: string): Promise<ApiSchemas['ConversationListResponse']> {
    const result = await backend.page({ archiveOnly: 'true', ...(cursor ? { cursor } : {}) })
    if (!disposed) mergeMetadata(result.conversations)
    return result
  }
  async function persist(operation: Promise<unknown>): Promise<void> {
    try { await operation }
    catch (error) {
      storageWarning.value = error instanceof Error ? error.message : 'Die Änderung konnte nicht gespeichert werden.'
      // On conflict, re-read authority. Preserve the unsent draft for recovery.
      if (!state.stream.busy.value) {
        const drafts = { ...state.drafts.records.value }
        try { await refresh(); state.drafts.records.value = { ...state.drafts.records.value, ...drafts } }
        catch { backendReady.value = false }
      }
    }
  }
  const create = state.conversations.create
  state.conversations.create = (title?: string) => {
    const conversation = create(title)
    sidebarIds.value = [conversation.id, ...sidebarIds.value].slice(0, 500)
    void persist(backend.ensure(conversation))
    return conversation
  }
  for (const action of ['rename', 'archive', 'restore'] as const) {
    const original = state.conversations[action]
    state.conversations[action] = (id: string, title?: string) => {
      if (!backendReady.value) return
      original(id, title ?? '')
      if (action === 'restore') sidebarIds.value = [id, ...sidebarIds.value.filter(value => value !== id)].slice(0, 500)
      void persist(backend.patch(id, action === 'rename' ? { title: title ?? '' } : { archived: action === 'archive' }))
    }
  }
  state.selectVariant = (id) => {
    const conversation = state.conversations.active.value
    if (!backendReady.value || state.stream.busy.value || !conversation || historyLoading.value) return false
    const conversationId = conversation.id
    const leaf = conversation.activeLeafMessageId
    if (leaf) for (const message of state.visible.value) state.preferredLeaves.value[message.id] = leaf
    historyLoading.value = true
    void (async () => {
      try {
        const result = await backend.path(conversationId, { messageId: id, ...(state.preferredLeaves.value[id] ? { preferredLeafId: state.preferredLeaves.value[id] } : {}) })
        if (disposed || state.conversations.activeId.value !== conversationId || state.stream.busy.value) return
        if (!result.leafMessageId) return
        // Persist selection before presenting the resolved path.
        await backend.patch(conversationId, { activeLeafMessageId: result.leafMessageId })
        result.conversation = { ...result.conversation, activeLeafMessageId: result.leafMessageId, version: backend.versions.get(conversationId)! }
        applyPath(result)
      }
      catch (error) { historyError.value = error instanceof Error ? error.message : 'Die Variante konnte nicht geladen werden.' }
      finally { historyLoading.value = false }
    })()
    return true
  }
  const remove = state.remove
  state.remove = (id) => {
    if (!backendReady.value) return
    cache.invalidate(id)
    windows.value = Object.fromEntries(Object.entries(windows.value).filter(([key]) => key !== id))
    state.pathBoundaries.value = Object.fromEntries(Object.entries(state.pathBoundaries.value).filter(([key]) => key !== id))
    remove(id)
    void persist(backend.remove(id))
  }
  function flushCache(): void {
    try { localStorage.setItem(CHAT_CACHE_KEY, JSON.stringify({ version: 2, preferredLeaves: state.preferredLeaves.value })) }
    catch { storageWarning.value = 'Der lokale Cache ist nicht verfügbar.' }
  }
  async function importLocalChats(): Promise<void> {
    if (importBusy.value || !backendReady.value) return
    importBusy.value = true
    try {
      const raw = localStorage.getItem(CHAT_STORAGE_KEY)
      const snapshot = raw ? parseChatSnapshot(raw) : null
      if (!snapshot) throw new Error('Der lokale Bestand ist ungültig und wurde erhalten.')
      const result = await backend.request<{ conflicts: unknown[], imported: string[], skipped: string[] }>('/conversations/import', 'POST', {
        conversations: Object.values(snapshot.conversations.conversations).map(({ titleGenerationAttempted: _attempted, ...c }) => c),
        messages: Object.values(snapshot.messages).map(m => ({ id: m.id, conversationId: m.conversationId, parentMessageId: m.parentMessageId, role: m.role, content: m.content, modelId: m.modelId ?? null, continuationCount: m.continuationCount ?? 0, errorCode: m.errorCode ?? null, errorMessage: m.errorMessage ?? null, editedFromMessageId: m.editedFromMessageId ?? null, status: m.status === 'submitting' || m.status === 'streaming' ? 'cancelled' : m.status, createdAt: m.createdAt, updatedAt: m.createdAt })),
        drafts: snapshot.drafts, activeConversationId: snapshot.conversations.activeConversationId,
      })
      if (result.conflicts.length) throw new Error('Der Import enthält Konflikte. Es wurden keine neuen Chats übernommen; der lokale Bestand bleibt erhalten.')
      await refresh()
      storageWarning.value = `${result.imported.length} Chats importiert, ${result.skipped.length} bereits vorhanden. Die lokale Sicherung bleibt erhalten.`
    }
    catch (error) { storageWarning.value = error instanceof Error ? error.message : 'Der Import ist fehlgeschlagen.' }
    finally { importBusy.value = false }
  }
  onMounted(async () => {
    try {
      importAvailable.value = Boolean(localStorage.getItem(CHAT_STORAGE_KEY))
      await refresh()
      // Recover an explicitly saved reader position with bounded active-chat
      // paging. No inactive messages are loaded. At most 20 pages (1,000 rows).
      const scrollRaw = localStorage.getItem('noris-ai:chat-scroll:v1')
      if (scrollRaw && scrollRaw.length <= 16000) {
        const positions: unknown = JSON.parse(scrollRaw)
        const active = state.conversations.activeId.value
        const entry = Array.isArray(positions) ? positions.find(item => Array.isArray(item) && item[0] === active) : undefined
        const anchor = entry?.[1]?.following === false && typeof entry[1].messageId === 'string' ? entry[1].messageId : null
        for (let page = 0; anchor && !state.messages.value[anchor] && windows.value[active ?? '']?.nextCursor && page < 20; page++) await loadOlder()
      }
      await transport.connect?.()
      // Only variant-view preferences are read from cache. Message content and
      // active conversation always come from the database.
      const cached = localStorage.getItem(CHAT_CACHE_KEY)
      if (cached && cached.length <= 256000) {
        const value: unknown = JSON.parse(cached)
        if (value && typeof value === 'object' && 'preferredLeaves' in value && value.preferredLeaves && typeof value.preferredLeaves === 'object') {
          state.preferredLeaves.value = Object.fromEntries(Object.entries(value.preferredLeaves).filter(([node, leaf]) => /^[0-9a-f-]{36}$/.test(node) && typeof leaf === 'string' && /^[0-9a-f-]{36}$/.test(leaf)).slice(-2000))
        }
      }
      const offline: unknown = JSON.parse(localStorage.getItem(OFFLINE_DRAFTS_KEY) ?? '{}')
      if (offline && typeof offline === 'object' && !Array.isArray(offline)) {
        for (const [key, text] of Object.entries(offline)) if (typeof text === 'string' && text.length <= 64000 && (key === '__new__' || /^[0-9a-f-]{36}$/.test(key))) {
          pendingDrafts[key] = text
          state.drafts.records.value[key] = text
        }
        if (Object.keys(pendingDrafts).length) storageWarning.value = 'Ein lokal noch nicht gespeicherter Entwurf wurde wiederhergestellt.'
      }
      const running = Object.values(state.messages.value).find(m => m.generationId && (m.status === 'streaming' || m.status === 'submitting'))
      if (running) state.resume(running.id)
    }
    catch (error) { storageWarning.value = error instanceof Error ? error.message : 'Chats konnten nicht geladen werden.' }
  })
  watch([state.preferredLeaves, state.conversations.activeId], () => {
    clearTimeout(timer); timer = setTimeout(flushCache, 120)
  }, { deep: true })
  watch(state.conversations.activeId, id => {
    if (backendReady.value) {
      void persist(backend.preferences(id))
      historyError.value = null
      if (id) void loadConversation(id)
      else { historyLoading.value = false; viewRequest?.abort.abort() }
    }
  })
  watch(state.generatingConversationId, (id, previous) => {
    if (!id && previous) { cache.invalidate(previous); void loadConversation(previous, true); evict() }
  })
  watch(state.drafts.records, () => {
    if (backendReady.value) {
      for (const [key, content] of Object.entries(state.drafts.records.value)) if (sentDrafts[key] !== content) pendingDrafts[key] = content
      savePendingDrafts()
    }
    clearTimeout(draftTimer)
    draftTimer = setTimeout(() => {
      if (!backendReady.value) return
      for (const [key, content] of Object.entries(state.drafts.records.value)) {
        if (sentDrafts[key] === content || (key !== '__new__' && !state.conversations.records.value[key])) continue
        void persist(backend.draft(key, content).then(() => {
          sentDrafts[key] = content
          if (pendingDrafts[key] === content) pendingDrafts = Object.fromEntries(Object.entries(pendingDrafts).filter(([id]) => id !== key))
          savePendingDrafts()
        }))
      }
      flushCache()
    }, 300)
  }, { deep: true, flush: 'sync' })
  onUnmounted(() => { disposed = true; viewRequest?.abort.abort(); clearTimeout(timer); clearTimeout(draftTimer); flushCache(); transport.dispose?.() })
  const pagination = {
    conversations: computed(() => sidebarIds.value.flatMap(id => { const c = state.conversations.records.value[id]; return c && !c.archivedAt ? [c] : [] })),
    sidebarLoading, sidebarError, hasMore: computed(() => Boolean(nextCursor.value)), loadMore,
    historyLoading, historyError, olderLoading,
    hasOlder: computed(() => Boolean(windows.value[state.conversations.activeId.value ?? '']?.nextCursor)),
    loadOlder, retryHistory: () => { const id = state.conversations.activeId.value; if (id) void loadConversation(id, true) },
    search, loadArchive,
  }
  return { pagination, storageWarning, backendReady, importAvailable, importBusy, importLocalChats, refresh }
}
