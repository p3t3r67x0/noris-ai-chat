import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { CONVERSATIONS_STORAGE_KEY, normalizeTitle, parseConversationSnapshot } from '../lib/chat/conversations'
import type { Conversation, ConversationSnapshot } from '../lib/chat/conversations'
import { FALLBACK_TITLE, validGeneratedTitle } from '../lib/chat/titles'

export interface ConversationDependencies {
  id?: () => string
  now?: () => string
}

export function createConversationState(dependencies: ConversationDependencies = {}) {
  const records = ref<Record<string, Conversation>>({})
  const activeId = ref<string | null>(null)
  const id = dependencies.id ?? (() => globalThis.crypto.randomUUID())
  const now = dependencies.now ?? (() => new Date().toISOString())
  const get = (key: string): Conversation | undefined => Object.hasOwn(records.value, key) ? records.value[key] : undefined
  const active = computed(() => activeId.value === null ? null : get(activeId.value) ?? null)
  const visible = computed(() => Object.values(records.value).filter(item => item.archivedAt === null))
  const archived = computed(() => Object.values(records.value).filter(item => item.archivedAt !== null))

  function select(conversationId: string): void {
    const conversation = get(conversationId)
    if (conversation?.archivedAt === null) activeId.value = conversationId
  }

  function create(title?: string): Conversation {
    const time = now()
    const conversation: Conversation = { id: id(), title: normalizeTitle(title ?? 'Neuer Chat'), titleSource: title === undefined ? 'fallback' : 'manual', titleGenerationAttempted: title !== undefined, createdAt: time, updatedAt: time, archivedAt: null, activeLeafMessageId: null }
    records.value = { ...records.value, [conversation.id]: conversation }
    activeId.value = conversation.id
    return conversation
  }

  function rename(conversationId: string, title: string): void {
    const conversation = get(conversationId)
    if (conversation) { conversation.title = normalizeTitle(title); conversation.titleSource = 'manual'; conversation.titleGenerationAttempted = true }
  }

  function fitTitle(conversationId: string, expected: string, title: string): void {
    const conversation = get(conversationId)
    if (conversation && conversation.titleSource !== 'manual' && conversation.title === expected && (validGeneratedTitle(title) || title === FALLBACK_TITLE)) {
      conversation.title = title
      if (title === FALLBACK_TITLE) conversation.titleSource = 'fallback'
    }
  }

  function archive(conversationId: string): void {
    const conversation = get(conversationId)
    if (!conversation) return
    conversation.archivedAt = now()
    if (activeId.value === conversationId) activeId.value = null
  }

  function restore(conversationId: string): void {
    const conversation = get(conversationId)
    if (!conversation) return
    conversation.archivedAt = null
    select(conversationId)
  }

  function remove(conversationId: string): void {
    records.value = Object.fromEntries(Object.entries(records.value).filter(([key]) => key !== conversationId))
    if (activeId.value === conversationId) activeId.value = null
  }

  function snapshot(): ConversationSnapshot {
    return { version: 1, conversations: records.value, activeConversationId: activeId.value }
  }

  function hydrate(value: ConversationSnapshot): void {
    records.value = value.conversations
    activeId.value = value.activeConversationId
  }

  return { records, activeId, active, visible, archived, select, create, rename, fitTitle, archive, restore, remove, snapshot, hydrate }
}

export function useConversations() {
  const state = createConversationState()
  const storageWarning = ref<string | null>(null)
  let stopWatching: (() => void) | undefined
  onMounted(() => {
    try {
      const raw = window.localStorage.getItem(CONVERSATIONS_STORAGE_KEY)
      if (raw) {
        const saved = parseConversationSnapshot(raw)
        if (saved) state.hydrate(saved)
        else storageWarning.value = 'Gespeicherte Chats konnten nicht geladen werden.'
      }
    }
    catch { storageWarning.value = 'Lokaler Speicher ist nicht verfügbar.' }
    stopWatching = watch([state.records, state.activeId], () => {
      try { window.localStorage.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(state.snapshot())) }
      catch { storageWarning.value = 'Änderungen können gerade nicht lokal gespeichert werden.' }
    }, { deep: true })
  })
  onUnmounted(() => stopWatching?.())
  return { ...state, storageWarning }
}
