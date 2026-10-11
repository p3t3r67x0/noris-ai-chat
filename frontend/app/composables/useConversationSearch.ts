import { onScopeDispose, ref, watch } from 'vue'
import type { Ref } from 'vue'
import type { useChatBackend } from './useChatBackend'
import type { Conversation } from '../lib/chat/conversations'

type Pagination = ReturnType<typeof useChatBackend>['pagination']

// Coordinate the existing paginated PostgreSQL search. The command palette
// continues to filter local/demo conversations immediately.
export function useConversationSearch(open: Ref<boolean>, conversations: () => readonly Conversation[], pagination: () => Pagination | undefined) {
  const query = ref('')
  const results = ref<Conversation[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const cursor = ref<string | null>(null)
  let timer: ReturnType<typeof setTimeout> | undefined
  let controller: AbortController | undefined
  let revision = 0
  let resetting = false

  function cancel(): void {
    revision++
    controller?.abort()
    clearTimeout(timer)
  }

  async function search(more = false): Promise<void> {
    const source = pagination()
    if (!open.value || !source || (more && (loading.value || !cursor.value))) return
    const nextCursor = more ? cursor.value ?? undefined : undefined
    cancel()
    const request = new AbortController()
    controller = request
    const current = revision
    loading.value = true
    error.value = null
    try {
      const page = await source.search(query.value, request.signal, nextCursor)
      if (revision !== current || request.signal.aborted || !open.value) return
      const rows = page.conversations.map(row => ({ ...row, titleGenerationAttempted: row.titleSource !== 'fallback' }))
      results.value = more ? [...new Map([...results.value, ...rows].map(row => [row.id, row])).values()] : rows
      cursor.value = page.nextCursor ?? null
    }
    catch {
      if (revision === current && !request.signal.aborted) error.value = 'Die Suche ist fehlgeschlagen. Bitte versuche es erneut.'
    }
    finally {
      if (revision === current) loading.value = false
    }
  }

  watch(open, (opened) => {
    cancel()
    loading.value = false
    error.value = null
    cursor.value = null
    if (!opened) return
    resetting = true
    query.value = ''
    resetting = false
    results.value = [...conversations()]
    void search()
  }, { flush: 'sync' })

  watch(query, () => {
    if (resetting || !open.value || !pagination()) return
    cancel()
    cursor.value = null
    error.value = null
    loading.value = true
    // Only server requests are debounced; old rows remain visible meanwhile.
    timer = setTimeout(() => { void search() }, 200)
  }, { flush: 'sync' })

  onScopeDispose(cancel)
  return { query, results, loading, error, cursor, search }
}
