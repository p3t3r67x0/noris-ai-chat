import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { createConversationState } from './useConversations'
import type { ConversationDependencies } from './useConversations'
import { useChatStream } from './useChatStream'
import { MAX_MESSAGE_LENGTH, visiblePath } from '../lib/chat/types'
import type { ChatMessage, ChatTransport, MessageRecords } from '../lib/chat/types'
import type { ChatModelId } from './useModelSelection'
import { useChatDrafts } from './useChatDrafts'
import { siblingVariants, variantLeaf } from '../lib/chat/branches'
import { CHAT_STORAGE_KEY, parseChatSnapshot } from '../lib/chat/persistence'
import type { ChatSnapshot } from '../lib/chat/persistence'
import { CONVERSATIONS_STORAGE_KEY, parseConversationSnapshot } from '../lib/chat/conversations'

export function createChatState(transport: ChatTransport, dependencies: ConversationDependencies = {}, conversations = createConversationState(dependencies)) {
  const messages = ref<MessageRecords>({})
  const stream = useChatStream(transport)
  const id = dependencies.id ?? (() => globalThis.crypto.randomUUID())
  const now = dependencies.now ?? (() => new Date().toISOString())
  const visible = computed(() => conversations.active.value ? visiblePath(messages.value, conversations.active.value.id, conversations.active.value.activeLeafMessageId) : [])
  const generatingConversationId = ref<string | null>(null)
  const drafts = useChatDrafts(conversations.activeId)
  const preferredLeaves = ref<Record<string, string>>({})

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

  function generate(input: ChatMessage, modelId: ChatModelId, attempt = 1): void {
    const history = visiblePath(messages.value, input.conversationId, input.id).map(({ role, content }) => ({ role, content }))
    const reply = append(input.conversationId, input.id, 'assistant', '')
    generatingConversationId.value = input.conversationId
    void stream.start({ generationId: id(), conversationId: input.conversationId, inputMessageId: input.id, modelId, messages: history, attempt }, {
      delta: text => { reply.content += text },
      status: next => { reply.status = next },
    }).finally(() => { generatingConversationId.value = null })
  }

  function send(text: string, modelId: ChatModelId): boolean {
    const content = text.trim()
    if (stream.busy.value || !content || content.length > MAX_MESSAGE_LENGTH) return false
    const draftConversationId = conversations.activeId.value
    const conversation = conversations.active.value ?? conversations.create(content.slice(0, 70))
    const parent = visible.value.at(-1)
    if (parent?.role === 'user') return false
    if (conversation.activeLeafMessageId === null && conversation.title === 'Neuer Chat') conversations.rename(conversation.id, content.slice(0, 70))
    const input = append(conversation.id, conversation.activeLeafMessageId, 'user', content)
    generate(input, modelId)
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
    if (stream.busy.value || !content || content.length > MAX_MESSAGE_LENGTH || original?.role !== 'user' || original.conversationId !== conversations.activeId.value) return false
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
    regenerate(last.id, modelId)
  }
  function remove(conversationId: string): void {
    if (generatingConversationId.value === conversationId) stream.stop()
    messages.value = Object.fromEntries(Object.entries(messages.value).filter(([, message]) => message.conversationId !== conversationId))
    drafts.remove(conversationId)
    preferredLeaves.value = Object.fromEntries(Object.entries(preferredLeaves.value).filter(([node, leaf]) => Object.hasOwn(messages.value, node) && Object.hasOwn(messages.value, leaf)))
    conversations.remove(conversationId)
  }

  function snapshot(): ChatSnapshot { return { version: 1, conversations: conversations.snapshot(), messages: messages.value, drafts: drafts.records.value, preferredLeaves: preferredLeaves.value } }
  function hydrate(saved: ChatSnapshot): void {
    conversations.hydrate(saved.conversations)
    messages.value = saved.messages
    drafts.records.value = saved.drafts
    preferredLeaves.value = saved.preferredLeaves
  }
  const variants = (messageId: string) => siblingVariants(messages.value, messageId)
  return { conversations, messages, visible, stream, generatingConversationId, drafts, preferredLeaves, send, retry, newChat, remove, selectVariant, regenerate, edit, variants, snapshot, hydrate }
}

export function useChat(transport: ChatTransport) {
  const state = createChatState(transport)
  const storageWarning = ref<string | null>(null)
  let stopWatching: (() => void) | undefined
  let timer: ReturnType<typeof setTimeout> | undefined
  let persistenceAllowed = true
  function flush(): void {
    clearTimeout(timer)
    timer = undefined
    if (!persistenceAllowed) return
    try { window.localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(state.snapshot())) }
    catch { storageWarning.value = 'Änderungen können gerade nicht lokal gespeichert werden.' }
  }
  function externalChange(event: StorageEvent): void {
    if (event.key !== CHAT_STORAGE_KEY) return
    persistenceAllowed = false
    storageWarning.value = 'Chats wurden in einem anderen Tab geändert. Lade diese Seite neu, um den aktuellen Stand zu verwenden.'
  }
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
    stopWatching = watch([state.conversations.records, state.conversations.activeId, state.messages, state.drafts.records, state.preferredLeaves], () => {
      timer ??= setTimeout(flush, 120)
    }, { deep: true, flush: 'sync' })
    window.addEventListener('pagehide', flush)
    window.addEventListener('storage', externalChange)
  })
  onUnmounted(() => {
    state.stream.stop()
    stopWatching?.()
    if (typeof window !== 'undefined') {
      if (timer !== undefined) flush()
      window.removeEventListener('pagehide', flush)
      window.removeEventListener('storage', externalChange)
    }
  })
  return { ...state, storageWarning }
}
