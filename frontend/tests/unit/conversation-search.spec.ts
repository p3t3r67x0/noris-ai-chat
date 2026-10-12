import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, ref } from 'vue'
import { useConversationSearch } from '../../app/composables/useConversationSearch'
import type { useChatBackend } from '../../app/composables/useChatBackend'
import type { ApiSchemas } from '../../app/types/generated/api'

type Page = ApiSchemas['ConversationListResponse']
const row = (id: string): ApiSchemas['ConversationResponse'] => ({ id, title: `Synthetic ${id}`, titleSource: 'manual', version: 1, createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z', archivedAt: null, activeLeafMessageId: null, lastMessageAt: null })
const page = (ids: string[], nextCursor: string | null = null): Page => ({ conversations: ids.map(row), nextCursor, hasMore: Boolean(nextCursor) })
const scopes: ReturnType<typeof effectScope>[] = []
afterEach(() => { scopes.splice(0).forEach(scope => scope.stop()); vi.useRealTimers() })

function setup(search = vi.fn().mockResolvedValue(page(['recent'])), server = true) {
  const open = ref(false)
  const source = { search } as unknown as ReturnType<typeof useChatBackend>['pagination']
  const scope = effectScope()
  scopes.push(scope)
  const state = scope.run(() => useConversationSearch(open, () => [{ ...row('cached'), titleGenerationAttempted: true }], () => server ? source : undefined))!
  open.value = true
  return { open, request: search, ...state }
}

describe('existing conversation search coordination', () => {
  it('loads recent chats immediately, resets on reopen and debounces only server queries', async () => {
    vi.useFakeTimers()
    const state = setup()
    expect(state.request).toHaveBeenCalledTimes(1)
    await vi.runAllTicks()
    state.query.value = 'a'; state.query.value = 'ab'
    expect(state.loading.value).toBe(true)
    expect(state.results.value[0]?.id).toBe('recent')
    await vi.advanceTimersByTimeAsync(199)
    expect(state.request).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(state.request).toHaveBeenLastCalledWith('ab', expect.any(AbortSignal), undefined)
    state.open.value = false; state.open.value = true
    expect(state.query.value).toBe('')
    expect(state.request).toHaveBeenLastCalledWith('', expect.any(AbortSignal), undefined)
  })

  it('does not request or delay local/demo filtering', () => {
    const state = setup(vi.fn(), false)
    state.query.value = 'instant'
    expect(state.loading.value).toBe(false)
    expect(state.request).not.toHaveBeenCalled()
  })

  it('ignores late responses and errors even during the debounce window', async () => {
    vi.useFakeTimers()
    let resolve!: (value: Page) => void
    let reject!: (error: Error) => void
    const request = vi.fn().mockImplementationOnce(() => new Promise<Page>(done => { resolve = done })).mockImplementationOnce(() => new Promise<Page>((_, fail) => { reject = fail })).mockResolvedValue(page(['new']))
    const state = setup(request)
    state.query.value = 'old'
    expect(request.mock.calls[0]![1].aborted).toBe(true)
    resolve(page(['stale']))
    await vi.advanceTimersByTimeAsync(200)
    expect(state.results.value[0]?.id).toBe('cached')
    state.query.value = 'new'
    reject(new Error('late failure'))
    await vi.advanceTimersByTimeAsync(200)
    expect(state.results.value.map(row => row.id)).toEqual(['new'])
    expect(state.error.value).toBeNull()
    expect(state.loading.value).toBe(false)
  })

  it('pages the same query with its cursor, deduplicates and preserves rows on failure for retry', async () => {
    const request = vi.fn().mockResolvedValueOnce(page(['first'], 'next')).mockRejectedValueOnce(new Error('private detail')).mockResolvedValueOnce(page(['first', 'beyond-50']))
    const state = setup(request)
    await vi.waitFor(() => expect(state.cursor.value).toBe('next'))
    await state.search(true)
    expect(state.results.value.map(row => row.id)).toEqual(['first'])
    expect(state.error.value).toContain('Bitte versuche es erneut')
    expect(state.error.value).not.toContain('private detail')
    await state.search(true)
    expect(request).toHaveBeenLastCalledWith('', expect.any(AbortSignal), 'next')
    expect(state.results.value.map(row => row.id)).toEqual(['first', 'beyond-50'])
    expect(state.cursor.value).toBeNull()
    expect(state.error.value).toBeNull()
  })

  it('cancels pending requests and timers on close and scope disposal', async () => {
    vi.useFakeTimers()
    const request = vi.fn().mockResolvedValue(page(['recent']))
    const state = setup(request)
    state.query.value = 'pending'
    state.open.value = false
    await vi.advanceTimersByTimeAsync(250)
    expect(request).toHaveBeenCalledTimes(1)
    expect(request.mock.calls[0]![1].aborted).toBe(true)
    state.open.value = true
    scopes[0]!.stop()
    expect(request.mock.calls[1]![1].aborted).toBe(true)
  })
})
