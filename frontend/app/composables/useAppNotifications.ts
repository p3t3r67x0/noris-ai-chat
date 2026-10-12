import { hasInjectionContext, inject, nextTick, ref, watch } from 'vue'
import type { InjectionKey, Ref } from 'vue'
import { normalizeAppError, notificationKey } from '../lib/notifications/errors'
import type { ErrorContext, ErrorDiagnostics, NotificationSeverity } from '../lib/notifications/errors'

export const NOTIFICATION_DURATIONS = { success: 3500, info: 4500, warning: 7000, error: 12000 } as const
export const MAX_VISIBLE_NOTIFICATIONS = 3
export const MAX_PENDING_NOTIFICATIONS = 12
const DEDUPLICATION_MS = 10_000
type Toast = ReturnType<ReturnType<typeof useToast>['add']>
interface ToastPort { toasts: Ref<Toast[]>, add: (toast: Partial<Toast>) => Toast, remove: (id: string | number) => void }
export interface NotificationAction { label: string, onClick: () => unknown }
interface Notification { severity: NotificationSeverity, title: string, description?: string, key?: string, action?: NotificationAction, diagnostics?: ErrorDiagnostics, recoveryInContext?: boolean }

/** Ephemeral presentation only. Chat/upload/settings state remains with its existing owner. */
export function createAppNotifications(toast: ToastPort) {
  const details = ref<ErrorDiagnostics | null>(null)
  const alertAnnouncement = ref('')
  const statusAnnouncement = ref('')
  const announcementBatch = { alert: [] as string[], status: [] as string[] }
  let announcing = false
  const pending: Array<Notification & { key: string }> = []
  const active = new Set<string>()
  const recentlyClosed = new Map<string, number>()
  let overflow = 0
  let disposed = false
  const forget = (key: string) => { active.delete(key); recentlyClosed.set(key, Date.now()) }
  function pump(): void {
    if (disposed) return
    // Include closing cards until Nuxt UI removes them, preventing a fourth card during exit.
    while (pending.length && active.size < MAX_VISIBLE_NOTIFICATIONS && toast.toasts.value.length < MAX_VISIBLE_NOTIFICATIONS) {
      const notification = pending.shift()!
      const key = notification.key
      active.add(key)
      const channel = notification.severity === 'error' ? 'alert' : 'status'
      announcementBatch[channel].push([notification.title, notification.description, notification.action?.label].filter(Boolean).join(' '))
      if (!announcing) {
        announcing = true
        alertAnnouncement.value = ''; statusAnnouncement.value = ''
        void nextTick(() => {
          if (!disposed) {
            alertAnnouncement.value = announcementBatch.alert.join(' ')
            statusAnnouncement.value = announcementBatch.status.join(' ')
          }
          announcementBatch.alert.length = 0; announcementBatch.status.length = 0; announcing = false
        })
      }
      const actions: NonNullable<Toast['actions']> = []
      if (notification.action) actions.push({ label: notification.action.label, color: 'neutral', variant: 'soft', onClick: () => { void notification.action?.onClick() } })
      if (notification.diagnostics) actions.push({ label: 'Details', color: 'neutral', variant: 'ghost', onClick: () => { details.value = notification.diagnostics! } })
      toast.add({
        id: key, title: notification.title, ...(notification.description ? { description: notification.description } : {}),
        color: notification.severity, icon: { success: 'i-lucide-circle-check', info: 'i-lucide-info', warning: 'i-lucide-circle-alert', error: 'i-lucide-circle-alert' }[notification.severity],
        type: notification.severity === 'error' ? 'foreground' : 'background',
        duration: notification.action && !notification.recoveryInContext ? 0 : NOTIFICATION_DURATIONS[notification.severity],
        actions, progress: false, close: { variant: 'link', ...{ 'aria-label': 'Benachrichtigung schließen' } }, class: 'app-notification',
        // Visible cards are quiet; AppNotificationCenter owns live announcements.
        'onUpdate:open': (open) => { if (!open) forget(key) },
      })
    }
    if (overflow && pending.length < MAX_PENDING_NOTIFICATIONS) {
      pending.push({ key: `notification-overflow-${crypto.randomUUID()}`, severity: 'warning', title: 'Weitere Benachrichtigungen', description: `${overflow} weitere Meldungen. Betroffene Chats und Anhänge zeigen ihren Status und ihre Aktionen weiterhin an.` })
      overflow = 0
    }
  }
  const stopWatching = watch(() => toast.toasts.value.map(item => item.id), (ids, previous) => {
    for (const key of previous) if (typeof key === 'string' && active.has(key) && !ids.includes(key)) forget(key)
    pump()
  }, { flush: 'post' })
  function notify(notification: Notification): string | null {
    if (disposed) return null
    const key = notification.key ?? `notification-${crypto.randomUUID()}`
    const now = Date.now()
    for (const [id, time] of recentlyClosed) if (now - time >= DEDUPLICATION_MS) recentlyClosed.delete(id)
    if (active.has(key) || pending.some(item => item.key === key) || recentlyClosed.has(key)) return null
    if (recentlyClosed.size >= 200) recentlyClosed.delete(recentlyClosed.keys().next().value!)
    if (pending.length >= MAX_PENDING_NOTIFICATIONS) { recentlyClosed.set(key, now); overflow++; return null }
    pending.push({ ...notification, key })
    pump()
    return key
  }
  function reportError(cause: unknown, context: ErrorContext, action?: NotificationAction, recoveryInContext = true): string | null {
    const error = normalizeAppError(cause, context)
    return notify({ severity: error.severity, title: error.title, description: error.message, key: notificationKey(error, context), diagnostics: error.diagnostics, ...(action ? { action } : {}), recoveryInContext })
  }
  function dispose(): void { disposed = true; stopWatching(); pending.length = 0; active.clear(); recentlyClosed.clear(); details.value = null }
  return { notify, reportError, details, alertAnnouncement, statusAnnouncement, dismiss: toast.remove, dispose }
}
export type AppNotifications = ReturnType<typeof createAppNotifications>
export const appNotificationsKey: InjectionKey<AppNotifications> = Symbol('app-notifications')
export function useAppNotifications(): AppNotifications | undefined {
  return hasInjectionContext() ? inject(appNotificationsKey, undefined) : undefined
}
