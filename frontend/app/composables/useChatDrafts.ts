import { computed, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { NEW_CHAT_DRAFT } from '../lib/chat/types'
import { ABSOLUTE_MESSAGE_CHARS } from '../lib/chat/limits'

export function useChatDrafts(activeId: Ref<string | null>, records = ref<Record<string, string>>({})) {
  const key = (conversationId: string | null) => conversationId ?? NEW_CHAT_DRAFT
  const error = ref<string | null>(null)
  watch(activeId, () => { error.value = null })
  const draft = computed({
    get: () => Object.hasOwn(records.value, key(activeId.value)) ? records.value[key(activeId.value)] ?? '' : '',
    set: (text: string) => {
      if (text.length > ABSOLUTE_MESSAGE_CHARS * 2) {
        error.value = 'Der Entwurf ist zu groß. Der bisherige Entwurf wurde erhalten. Bitte verkürze die Eingabe.'
        return
      }
      error.value = null
      records.value = { ...records.value, [key(activeId.value)]: text }
    },
  })
  function clear(conversationId: string | null): void { error.value = null; records.value = { ...records.value, [key(conversationId)]: '' } }
  function remove(conversationId: string): void { records.value = Object.fromEntries(Object.entries(records.value).filter(([id]) => id !== conversationId)) }
  return { records, draft, error, clear, remove }
}
