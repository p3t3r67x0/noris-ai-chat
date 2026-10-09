import { computed, ref } from 'vue'
import type { Ref } from 'vue'
import { MAX_MESSAGE_LENGTH, NEW_CHAT_DRAFT } from '../lib/chat/types'

export function useChatDrafts(activeId: Ref<string | null>, records = ref<Record<string, string>>({})) {
  const key = (conversationId: string | null) => conversationId ?? NEW_CHAT_DRAFT
  const draft = computed({
    get: () => Object.hasOwn(records.value, key(activeId.value)) ? records.value[key(activeId.value)] ?? '' : '',
    set: (text: string) => { records.value = { ...records.value, [key(activeId.value)]: text.slice(0, MAX_MESSAGE_LENGTH * 2) } },
  })
  function clear(conversationId: string | null): void { records.value = { ...records.value, [key(conversationId)]: '' } }
  function remove(conversationId: string): void { records.value = Object.fromEntries(Object.entries(records.value).filter(([id]) => id !== conversationId)) }
  return { records, draft, clear, remove }
}
