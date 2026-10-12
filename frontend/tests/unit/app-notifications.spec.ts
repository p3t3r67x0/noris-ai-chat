import { readFileSync } from 'node:fs'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick, shallowRef } from 'vue'
import { createAppNotifications, MAX_PENDING_NOTIFICATIONS, NOTIFICATION_DURATIONS } from '../../app/composables/useAppNotifications'
import { ERROR_PRESENTATIONS, formatDiagnostics, normalizeAppError, notificationKey } from '../../app/lib/notifications/errors'

const context = { operation: 'generation' as const, conversationId: 'conversation', generationId: 'generation', requestId: 'request' }
const centers: ReturnType<typeof createAppNotifications>[] = []
afterEach(() => { centers.splice(0).forEach(center => center.dispose()); vi.useRealTimers() })
function fixture() {
  type Toast = Parameters<typeof createAppNotifications>[0]['toasts']['value'][number]
  const toasts = shallowRef<Toast[]>([])
  const add = vi.fn((options: Partial<Toast>): Toast => {
    const item = { id: 'id', ...options } as Toast
    void nextTick(() => {
      toasts.value = [...toasts.value, item]
      if (item.duration) setTimeout(() => remove(item.id), item.duration)
    })
    return item
  })
  const remove = (id: string | number) => {
    const item = toasts.value.find(item => item.id === id)
    item?.['onUpdate:open']?.(false)
    toasts.value = toasts.value.filter(item => item.id !== id)
  }
  const center = createAppNotifications({ toasts, add, remove })
  centers.push(center)
  return { center, toasts, add, remove }
}
const backendSources = ['chat/errors.py', 'llm/errors.py', 'main.py'].map(path => readFileSync(`../backend/src/noris_ai/${path}`, 'utf8')).join('\n')
const backendCodes = [...new Set([...backendSources.matchAll(/(?:^\s*"([A-Z_]+)":|error_response\(request, \d+, "([A-Z_]+)")/gm)].map(match => match[1] ?? match[2]!))]

describe('error contract presentation', () => {
  it.each(backendCodes)('normalizes the existing backend code %s without using the backend message', code => {
    expect(ERROR_PRESENTATIONS[code]).toBeDefined()
    const error = normalizeAppError({ error: { code, message: 'An internal error occurred; secret prompt stacktrace', request_id: 'request' } }, context)
    expect(error.code).toBe(code)
    expect(error.message).not.toMatch(/secret|stacktrace|internal error/)
    expect(error.message.length).toBeGreaterThan(15)
    expect(['transient', 'persistent', 'action', 'generation']).toContain(error.category)
    expect(error.recovery).toBeTruthy()
    expect(error.diagnostics.requestId).toBe('request')
  })
  it.each(Object.keys(ERROR_PRESENTATIONS))('normalizes client/runtime code %s', code => {
    expect(normalizeAppError({ code }, context).message).toBe(ERROR_PRESENTATIONS[code]!.message)
  })
  it('uses safe fallbacks for unknown exceptions and preserves unknown diagnostic codes', () => {
    expect(normalizeAppError(new Error('secret prompt'), context).message).not.toContain('secret')
    expect(normalizeAppError({ code: 'NEW_BACKEND_CODE', message: 'secret' }, context).code).toBe('NEW_BACKEND_CODE')
    expect(normalizeAppError(new TypeError('Failed to fetch'), context).code).toBe('NETWORK_ERROR')
    expect(normalizeAppError(new DOMException('timed out', 'TimeoutError'), context).code).toBe('TIMEOUT')
  })
  it('exports only allowlisted diagnostics and rejects arbitrary ID data', () => {
    const error = normalizeAppError({ code: 'PROVIDER_ERROR', requestId: 'request', prompt: 'PRIVATE', stack: 'PRIVATE' }, context, new Date('2026-10-12T10:00:00Z'))
    expect(formatDiagnostics(error.diagnostics)).toContain('Request-ID: request')
    expect(formatDiagnostics(error.diagnostics)).not.toContain('PRIVATE')
    expect(normalizeAppError({ code: 'secret text', request_id: 'Authorization: Bearer secret' }, { operation: 'upload' }).diagnostics).toMatchObject({ code: 'REQUEST_FAILED', requestId: null })
  })
  it('separates operations, conversations, requests, generations, resources and attempts', () => {
    const error = normalizeAppError({ code: 'TIMEOUT' }, context)
    const key = notificationKey(error, context)
    for (const changed of [{ operation: 'upload' as const }, { conversationId: 'other' }, { generationId: 'other' }, { resourceId: 'file' }]) expect(notificationKey(error, { ...context, ...changed })).not.toBe(key)
    expect(notificationKey(normalizeAppError({ code: 'TIMEOUT', requestId: 'other' }, context), context)).toBe(key)
    const requestContext = { operation: 'upload' as const }
    expect(notificationKey(normalizeAppError({ code: 'TIMEOUT', requestId: 'other' }, requestContext), requestContext)).not.toBe(notificationKey(normalizeAppError({ code: 'TIMEOUT', requestId: 'request' }, requestContext), requestContext))
    expect(notificationKey(normalizeAppError({ code: 'TIMEOUT' }, requestContext), { ...requestContext, attemptId: '1' })).not.toBe(notificationKey(normalizeAppError({ code: 'TIMEOUT' }, requestContext), { ...requestContext, attemptId: '2' }))
  })
})

describe('central Nuxt UI presentation', () => {
  it('deduplicates even before Nuxt UI inserts the card and announces exactly once', async () => {
    const { center, toasts, add } = fixture()
    expect(center.reportError({ code: 'TIMEOUT' }, context)).not.toBeNull()
    expect(center.reportError({ code: 'TIMEOUT' }, context)).toBeNull()
    await nextTick()
    expect(toasts.value).toHaveLength(1)
    expect(add).toHaveBeenCalledOnce()
    expect(center.alertAnnouncement.value).toContain('Antwort konnte nicht erstellt werden.')
  })
  it('does not permanently suppress a later independent failure or a later event', async () => {
    vi.useFakeTimers()
    const { center, toasts, remove } = fixture()
    center.reportError({ code: 'NETWORK_ERROR' }, context)
    await nextTick()
    remove(toasts.value[0]!.id)
    expect(center.reportError({ code: 'NETWORK_ERROR' }, context)).toBeNull()
    expect(center.reportError({ code: 'NETWORK_ERROR' }, { ...context, generationId: 'next' })).not.toBeNull()
    await vi.advanceTimersByTimeAsync(10001)
    expect(center.reportError({ code: 'NETWORK_ERROR' }, context)).not.toBeNull()
  })
  it('sets the documented lifetimes and keeps a necessary action without contextual recovery', async () => {
    const { center, add } = fixture()
    for (const severity of ['success', 'info', 'warning'] as const) center.notify({ severity, title: severity })
    await nextTick()
    expect(add.mock.calls.map(([toast]) => toast.duration)).toEqual([3500, 4500, 7000])
    const other = fixture()
    other.center.reportError({ code: 'TIMEOUT' }, context, { label: 'Retry', onClick: vi.fn() }, false)
    await nextTick()
    expect(other.add.mock.calls[0]?.[0].duration).toBe(0)
    expect(NOTIFICATION_DURATIONS.error).toBe(12000)
  })
  it('keeps at most three simultaneous cards and drains the queue after expiration', async () => {
    vi.useFakeTimers()
    const { center, toasts, add } = fixture()
    for (let i = 0; i < 5; i++) center.notify({ severity: 'success', title: `operation-${i}` })
    await nextTick()
    expect(toasts.value).toHaveLength(3)
    expect(add).toHaveBeenCalledTimes(3)
    await vi.advanceTimersByTimeAsync(3501)
    expect(toasts.value).toHaveLength(2)
    expect(add).toHaveBeenCalledTimes(5)
  })
  it('bounds pending notifications and summarizes overflow', async () => {
    const { center, toasts, add, remove } = fixture()
    for (let i = 0; i < 50; i++) center.notify({ severity: 'error', title: `operation-${i}` })
    await nextTick()
    for (let i = 0; i < MAX_PENDING_NOTIFICATIONS + 6; i++) {
      if (toasts.value[0]) remove(toasts.value[0].id)
      await nextTick(); await nextTick()
    }
    expect(add.mock.calls.length).toBeLessThanOrEqual(3 + MAX_PENDING_NOTIFICATIONS + 1)
    expect(add.mock.calls.some(([toast]) => toast.title === 'Weitere Benachrichtigungen')).toBe(true)
  })
  it('runs recovery only on explicit action and allows safe diagnostic details', async () => {
    const { center, toasts } = fixture()
    const retry = vi.fn()
    center.reportError({ code: 'PROVIDER_ERROR' }, context, { label: 'Erneut versuchen', onClick: retry })
    await nextTick()
    expect(retry).not.toHaveBeenCalled()
    const retryAction = toasts.value[0]!.actions?.[0]?.onClick
    expect(typeof retryAction).toBe('function')
    if (typeof retryAction === 'function') retryAction(new MouseEvent('click'))
    expect(retry).toHaveBeenCalledOnce()
    const detailsAction = toasts.value[0]!.actions?.[1]?.onClick
    expect(typeof detailsAction).toBe('function')
    if (typeof detailsAction === 'function') detailsAction(new MouseEvent('click'))
    expect(center.details.value?.requestId).toBe('request')
  })
  it('uses separate assertive errors and polite informational announcements', async () => {
    const { center } = fixture()
    center.notify({ severity: 'info', title: 'Entwurf wiederhergestellt.' })
    center.reportError({ code: 'TIMEOUT' }, context)
    await nextTick()
    expect(center.statusAnnouncement.value).toBe('Entwurf wiederhergestellt.')
    expect(center.alertAnnouncement.value).not.toContain('Entwurf wiederhergestellt.')
  })
})
