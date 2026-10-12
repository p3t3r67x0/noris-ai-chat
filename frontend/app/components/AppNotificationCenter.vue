<script setup lang="ts">
import { computed, onMounted, onUnmounted, provide } from 'vue'
import { appNotificationsKey, createAppNotifications } from '../composables/useAppNotifications'
import { useCopy } from '../composables/useCopy'
import { formatDiagnostics } from '../lib/notifications/errors'

const notifications = createAppNotifications(useToast())
provide(appNotificationsKey, notifications)
const { details, alertAnnouncement, statusAnnouncement } = notifications
const open = computed({ get: () => Boolean(details.value), set: (value: boolean) => { if (!value) details.value = null } })
const { copy, copied, copyError } = useCopy()
const diagnosticText = computed(() => details.value ? formatDiagnostics(details.value) : '')
function viewport(): void {
  const visual = window.visualViewport
  const height = visual?.scale === 1 ? visual.height : window.innerHeight
  const offset = visual?.scale === 1 ? visual.offsetTop : 0
  document.documentElement.style.setProperty('--notification-viewport-height', `${height}px`)
  document.documentElement.style.setProperty('--notification-viewport-offset', `${offset}px`)
}
onMounted(() => {
  viewport()
  window.visualViewport?.addEventListener('resize', viewport)
  window.visualViewport?.addEventListener('scroll', viewport)
  window.addEventListener('resize', viewport)
})
onUnmounted(() => {
  notifications.dispose()
  window.visualViewport?.removeEventListener('resize', viewport)
  window.visualViewport?.removeEventListener('scroll', viewport)
  window.removeEventListener('resize', viewport)
  document.documentElement.style.removeProperty('--notification-viewport-height')
  document.documentElement.style.removeProperty('--notification-viewport-offset')
})
</script>

<template>
  <slot />
  <!-- The pinned Reka version hides its announcer with aria-hidden. Announce once here. -->
  <p role="alert" aria-live="assertive" aria-atomic="true" class="sr-only" data-notification-announcer="alert">{{ alertAnnouncement }}</p>
  <p role="status" aria-live="polite" aria-atomic="true" class="sr-only" data-notification-announcer="status">{{ statusAnnouncement }}</p>
  <UModal v-model:open="open" title="Fehlerdetails" description="Diese Diagnose enthält nur technische Kennungen und keine Chat-Inhalte." :ui="{ overlay: 'z-[70]', content: 'z-[80]' }">
    <template #body>
      <pre class="notification-diagnostics" tabindex="0">{{ diagnosticText }}</pre>
      <p v-if="copyError" role="status" class="text-sm text-error">{{ copyError }}</p>
    </template>
    <template #footer>
      <UButton color="neutral" variant="soft" :label="copied ? 'Kopiert' : 'Diagnose kopieren'" :icon="copied ? 'i-lucide-check' : 'i-lucide-copy'" @click="copy(diagnosticText)" />
      <UButton color="neutral" variant="ghost" label="Schließen" @click="open = false" />
    </template>
  </UModal>
</template>
