<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { Conversation } from '../../lib/chat/conversations'
import { useWorkspace } from '../../composables/useWorkspace'
import { useAppLocale } from '../../composables/useAppLocale'
import SettingsRow from '../../components/settings/SettingsRow.vue'
import DeleteConversationDialog from '../../components/chat/DeleteConversationDialog.vue'
import { normalizeAppError } from '../../lib/notifications/errors'
const { chat } = useWorkspace()
const { t } = useAppLocale()
const ids = ref<string[]>([])
const cursor = ref<string | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const rows = computed(() => chat.pagination ? ids.value.flatMap(id => {
  const c = chat.conversations.records.value[id]
  return c?.archivedAt ? [c] : []
}) : chat.conversations.archived.value)
async function load(more = false): Promise<void> {
  if (!chat.pagination || loading.value) return
  loading.value = true; error.value = null
  try {
    const result = await chat.pagination.loadArchive(more ? cursor.value ?? undefined : undefined)
    ids.value = [...new Set([...(more ? ids.value : []), ...result.conversations.map(c => c.id)])]
    cursor.value = result.nextCursor ?? null
  }
  catch (cause) { error.value = normalizeAppError(cause, { operation: 'archive' }).message }
  finally { loading.value = false }
}
onMounted(() => { void load() })
const target = ref<Conversation | null>(null)
const returnFocus = ref<HTMLElement | null>(null)
const open = computed({ get: () => target.value !== null, set: (value: boolean) => { if (!value) target.value = null } })
function showDelete(conversation: Conversation, event: MouseEvent): void { target.value = conversation; returnFocus.value = event.currentTarget as HTMLElement }
function restore(conversation: Conversation): void {
  chat.conversations.restore(conversation.id)
  document.getElementById('archive')?.focus()
}
</script>

<template>
  <div class="settings-rows">
    <section id="archive" :aria-label="t('archived')" tabindex="-1" class="settings-rows">
      <p v-if="error" role="alert">{{ error }} <UButton color="neutral" variant="link" :label="t('retry')" @click="load()" /></p>
      <details v-if="chat.storageWarning.value" class="text-sm text-muted"><summary>Sicherung und Änderungen prüfen</summary><p>{{ chat.storageWarning.value }}</p><UButton v-if="chat.retryPersistence.value" color="neutral" variant="link" label="Erneut speichern" @click="chat.retryPersistence.value?.()" /></details>
      <p v-if="loading" role="status" class="text-muted">{{ t('archiveLoading') }}</p>
      <p v-else-if="!rows.length && !error" class="text-muted">{{ t('emptyArchive') }}</p>
      <SettingsRow v-for="conversation in rows" :key="conversation.id" :title="conversation.title">
        <UButton icon="i-lucide-undo-2" color="neutral" variant="ghost" class="touch-control" :aria-label="`${conversation.title} ${t('restore').toLowerCase()}`" @click="restore(conversation)" />
        <UButton icon="i-lucide-trash-2" color="neutral" variant="ghost" class="touch-control" :aria-label="`${conversation.title} ${t('delete').toLowerCase()}`" @click="showDelete(conversation, $event)" />
      </SettingsRow>
      <UButton v-if="cursor" color="neutral" variant="outline" :label="t('moreArchived')" :loading="loading" @click="load(true)" />
    </section>
    <DeleteConversationDialog v-model:open="open" :conversation="target" :remove-conversation="chat.remove" :return-focus="returnFocus" />
  </div>
</template>
