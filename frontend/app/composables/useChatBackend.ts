import { onMounted, onUnmounted, ref, watch } from 'vue'
import type { createChatState } from './useChat'
import type { ChatTransport } from '../lib/chat/types'
import { conversationFromServer } from '../lib/chat/backend'
import { CHAT_STORAGE_KEY, parseChatSnapshot } from '../lib/chat/persistence'

export const CHAT_CACHE_KEY = 'noris-ai:chat-cache:v1'
const OFFLINE_DRAFTS_KEY = 'noris-ai:offline-drafts:v1'

/** Synchronizes the existing state through explicit resource operations. */
export function useChatBackend(state: ReturnType<typeof createChatState>, transport: ChatTransport) {
  const backend = transport.backend!
  const storageWarning = ref<string | null>(null)
  const backendReady = ref(false)
  const importAvailable = ref(false)
  const importBusy = ref(false)
  let disposed = false
  let timer: ReturnType<typeof setTimeout> | undefined
  let draftTimer: ReturnType<typeof setTimeout> | undefined
  let sentDrafts: Record<string, string> = {}
  let pendingDrafts: Record<string, string> = {}
  function savePendingDrafts(): void {
    try { localStorage.setItem(OFFLINE_DRAFTS_KEY, JSON.stringify(pendingDrafts)) }
    catch { storageWarning.value = 'Der lokale Entwurf konnte nicht gesichert werden.' }
  }

  backend.onConversation = (value) => {
    const existing = state.conversations.records.value[value.id]
    if (existing) Object.assign(existing, conversationFromServer(value))
  }
  async function refresh(): Promise<void> {
    const snapshot = await backend.load()
    if (disposed) return
    state.hydrate(snapshot)
    sentDrafts = { ...snapshot.drafts }
    backendReady.value = true
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
    void persist(backend.ensure(conversation))
    return conversation
  }
  for (const action of ['rename', 'archive', 'restore'] as const) {
    const original = state.conversations[action]
    state.conversations[action] = (id: string, title?: string) => {
      if (!backendReady.value) return
      original(id, title ?? '')
      void persist(backend.patch(id, action === 'rename' ? { title: title ?? '' } : { archived: action === 'archive' }))
    }
  }
  const selectVariant = state.selectVariant
  state.selectVariant = (id) => {
    if (!backendReady.value || !selectVariant(id)) return false
    const conversation = state.conversations.active.value!
    void persist(backend.patch(conversation.id, { activeLeafMessageId: conversation.activeLeafMessageId! }))
    return true
  }
  const remove = state.remove
  state.remove = (id) => {
    if (!backendReady.value) return
    remove(id)
    void persist(backend.remove(id))
  }
  function flushCache(): void {
    try { localStorage.setItem(CHAT_CACHE_KEY, JSON.stringify(state.snapshot())) }
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
        messages: Object.values(snapshot.messages).map(m => ({ ...m, status: m.status === 'submitting' || m.status === 'streaming' ? 'cancelled' : m.status, updatedAt: m.createdAt })),
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
      // Only variant-view preferences are read from cache. Message content and
      // active conversation always come from the database.
      const cached = localStorage.getItem(CHAT_CACHE_KEY)
      const cache = cached ? parseChatSnapshot(cached) : null
      if (cache) state.preferredLeaves.value = Object.fromEntries(Object.entries(cache.preferredLeaves).filter(([node, leaf]) => state.messages.value[node]?.conversationId === state.messages.value[leaf]?.conversationId && state.messages.value[node]))
      const offline: unknown = JSON.parse(localStorage.getItem(OFFLINE_DRAFTS_KEY) ?? '{}')
      if (offline && typeof offline === 'object' && !Array.isArray(offline)) {
        for (const [key, text] of Object.entries(offline)) if (typeof text === 'string' && text.length <= 64000 && (key === '__new__' || state.conversations.records.value[key])) {
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
  watch([state.messages, state.conversations.records, state.conversations.activeId], () => {
    clearTimeout(timer); timer = setTimeout(flushCache, 120)
  }, { deep: true })
  watch(state.conversations.activeId, id => { if (backendReady.value) void persist(backend.preferences(id)) })
  watch(state.drafts.records, () => {
    if (backendReady.value) {
      for (const [key, content] of Object.entries(state.drafts.records.value)) if (sentDrafts[key] !== content) pendingDrafts[key] = content
      savePendingDrafts()
    }
    clearTimeout(draftTimer)
    draftTimer = setTimeout(() => {
      if (!backendReady.value) return
      for (const [key, content] of Object.entries(state.drafts.records.value)) {
        if (sentDrafts[key] === content) continue
        void persist(backend.draft(key, content).then(() => {
          sentDrafts[key] = content
          if (pendingDrafts[key] === content) pendingDrafts = Object.fromEntries(Object.entries(pendingDrafts).filter(([id]) => id !== key))
          savePendingDrafts()
        }))
      }
      flushCache()
    }, 300)
  }, { deep: true, flush: 'sync' })
  onUnmounted(() => { disposed = true; clearTimeout(timer); clearTimeout(draftTimer); flushCache(); transport.dispose?.() })
  return { storageWarning, backendReady, importAvailable, importBusy, importLocalChats, refresh }
}
