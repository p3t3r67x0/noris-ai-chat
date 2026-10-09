import { computed, onMounted, onUnmounted, ref } from 'vue'
import { createConversationState, useConversations } from './useConversations'
import type { ConversationDependencies } from './useConversations'
import { useChatStream } from './useChatStream'
import { MAX_MESSAGE_LENGTH, visiblePath } from '../lib/chat/types'
import type { ChatMessage, ChatTransport, MessageRecords } from '../lib/chat/types'
import type { ChatModelId } from './useModelSelection'

export function createChatState(transport: ChatTransport, dependencies: ConversationDependencies = {}, conversations = createConversationState(dependencies)) {
  const messages = ref<MessageRecords>({})
  const stream = useChatStream(transport)
  const id = dependencies.id ?? (() => globalThis.crypto.randomUUID())
  const now = dependencies.now ?? (() => new Date().toISOString())
  const visible = computed(() => conversations.active.value ? visiblePath(messages.value, conversations.active.value.id, conversations.active.value.activeLeafMessageId) : [])
  const generatingConversationId = ref<string | null>(null)

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
    const conversation = conversations.active.value ?? conversations.create(content.slice(0, 70))
    const parent = visible.value.at(-1)
    if (parent?.role === 'user') return false
    if (conversation.activeLeafMessageId === null && conversation.title === 'Neuer Chat') conversations.rename(conversation.id, content.slice(0, 70))
    const input = append(conversation.id, conversation.activeLeafMessageId, 'user', content)
    generate(input, modelId)
    return true
  }

  function newChat(): void { conversations.create() }
  function retry(modelId: ChatModelId): void {
    if (stream.busy.value) return
    const last = visible.value.at(-1)
    if (last?.role !== 'assistant' || last.status !== 'failed' || !last.parentMessageId) return
    const input = messages.value[last.parentMessageId]
    if (input?.role !== 'user') return
    const attempts = Object.values(messages.value).filter(message => message.parentMessageId === input.id && message.role === 'assistant').length
    generate(input, modelId, attempts + 1)
  }
  function remove(conversationId: string): void {
    if (generatingConversationId.value === conversationId) stream.stop()
    messages.value = Object.fromEntries(Object.entries(messages.value).filter(([, message]) => message.conversationId !== conversationId))
    conversations.remove(conversationId)
  }

  return { conversations, messages, visible, stream, generatingConversationId, send, retry, newChat, remove, append, generate }
}

export function useChat(transport: ChatTransport) {
  const conversations = useConversations()
  const state = createChatState(transport, {}, conversations)
  onMounted(() => {
    // PR 2 keeps metadata; validated message persistence is introduced with branches.
    for (const conversation of Object.values(conversations.records.value)) conversation.activeLeafMessageId = null
  })
  onUnmounted(state.stream.stop)
  return { ...state, storageWarning: conversations.storageWarning }
}
