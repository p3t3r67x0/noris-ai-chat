import { onScopeDispose, ref, watch } from 'vue'
import type { Ref } from 'vue'
import type { ApiSchemas } from '../types/generated/api'
import type { useChatBackend } from './useChatBackend'
import type { Conversation } from '../lib/chat/conversations'
import { normalizeAppError } from '../lib/notifications/errors'
import type { ErrorDiagnostics } from '../lib/notifications/errors'

type Pagination = ReturnType<typeof useChatBackend>['pagination']

// Coordinate the existing paginated PostgreSQL search. The command palette
// continues to filter local/demo conversations immediately.
export function useConversationSearch(open: Ref<boolean>, conversations: () => readonly Conversation[], pagination: () => Pagination | undefined) {
  const query = ref('')
  const results = ref<Conversation[]>([])
  const matches = ref<ApiSchemas['ConversationSearchMatch'][]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const diagnostics = ref<ErrorDiagnostics | null>(null)
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
      matches.value = more ? [...matches.value, ...(page.matches ?? [])] : page.matches ?? []
      cursor.value = page.nextCursor ?? null
    }
    catch (cause) {
      if (revision === current && !request.signal.aborted) {
        const failure = normalizeAppError(cause, { operation: 'search', attemptId: String(current) })
        error.value = failure.message; diagnostics.value = failure.diagnostics
      }
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
    matches.value = []
    resetting = false
    results.value = [...conversations()]
    void search()
  }, { flush: 'sync' })

  function scheduleSearch(): void {
    if (resetting || !open.value || !pagination()) return
    cancel()
    cursor.value = null
    error.value = null
    loading.value = true
    // Only server requests are debounced; old rows remain visible meanwhile.
    timer = setTimeout(() => { void search() }, 200)
  }
  watch(query, scheduleSearch, { flush: 'sync' })
  // Metadata broadcasts are authoritative for first sends, title changes,
  // archives and deletions, including updates from other browser tabs. Requery
  // on the server so title matching and cursor boundaries use the same rule.
  watch(() => pagination()?.revision?.value, scheduleSearch, { flush: 'sync' })

  onScopeDispose(cancel)
  return { query, results, matches, loading, error, diagnostics, cursor, search }
}
