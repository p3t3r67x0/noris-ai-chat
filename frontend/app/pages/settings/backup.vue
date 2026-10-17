<script setup lang="ts">
import { computed, ref } from 'vue'
import SettingsRow from '../../components/settings/SettingsRow.vue'
import { useWorkspace } from '../../composables/useWorkspace'
import { useAppLocale } from '../../composables/useAppLocale'

const { chat } = useWorkspace()
const { t } = useAppLocale()
const status = chat.persistenceStatus
const notice = chat.storageWarning
const retrying = ref(false)
const stateLabel = computed(() => status.value.blocked ? t('backupBlocked')
  : status.value.failedOperations ? t('backupFailed')
    : status.value.pendingOperations || status.value.pendingDrafts ? t('backupPending')
      : status.value.ready ? t('backupActive') : t('backupPreparing'))
async function retry(): Promise<void> {
  if (retrying.value || !chat.retryPersistence.value) return
  retrying.value = true
  try { await chat.retryPersistence.value() }
  finally { retrying.value = false }
}
function reload(): void { window.location.reload() }
</script>

<template>
  <div class="settings-rows" data-backup-settings>
    <SettingsRow id="persistence-status" :title="t('persistenceStatus')" :description="t(status.storage === 'server' ? 'backupServer' : 'backupLocal')">
      <span role="status" aria-live="polite" class="text-sm" :class="status.blocked || status.failedOperations ? 'text-error' : 'text-muted'" data-persistence-state>{{ stateLabel }}</span>
    </SettingsRow>
    <SettingsRow :title="t('backupPendingWrites')" :description="t('backupPendingDescription')"><span data-pending-operations>{{ status.pendingOperations }}</span></SettingsRow>
    <SettingsRow :title="t('backupPendingDrafts')"><span data-pending-drafts>{{ status.pendingDrafts }}</span></SettingsRow>
    <SettingsRow :title="t('backupFailedWrites')"><span data-failed-operations>{{ status.failedOperations }}</span></SettingsRow>
    <SettingsRow :title="t('backupRestoredDrafts')" :description="t('backupRestoredDescription')"><span data-restored-drafts>{{ status.restoredDrafts }}</span></SettingsRow>
    <SettingsRow v-if="notice" :title="t('backupNotice')" :description="notice" />
    <SettingsRow v-if="status.lastError" :title="t('backupLastError')" :description="status.lastError" />
    <SettingsRow v-if="status.recovery === 'reload'" :title="t('backupRecovery')" :description="t('backupReloadDescription')">
      <UButton color="neutral" variant="outline" class="settings-action" :label="t('backupReload')" @click="reload" />
    </SettingsRow>
    <SettingsRow v-else-if="chat.retryPersistence.value" :title="t('backupRecovery')" :description="t('backupRecoveryDescription')">
      <UButton color="neutral" variant="outline" class="settings-action" :label="t('backupRetry')" :loading="retrying" :disabled="retrying" @click="retry" />
    </SettingsRow>
  </div>
</template>
