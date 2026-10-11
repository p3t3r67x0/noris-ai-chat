<script setup lang="ts">
import { computed, ref } from 'vue'
import SettingsRow from './SettingsRow.vue'
import { useAppLocale } from '../../composables/useAppLocale'

const props = defineProps<{ importAvailable: boolean, importReady: boolean, importBusy: boolean, importLocalChats: () => Promise<void>, importFeedback: string | null }>()
const { t } = useAppLocale()
const pending = ref(false)
const busy = computed(() => props.importBusy || pending.value)
const confirmationOpen = ref(false)
const importOpen = computed({ get: () => confirmationOpen.value, set: (value: boolean) => { if (!busy.value) confirmationOpen.value = value } })

async function importChats(): Promise<void> {
  if (!confirmationOpen.value || busy.value || !props.importAvailable || !props.importReady) return
  pending.value = true
  try { await props.importLocalChats() }
  finally { pending.value = false; confirmationOpen.value = false }
}
</script>

<template>
  <SettingsRow v-if="importAvailable" id="local-import" :title="t('importTitle')" :description="t('importDescription')">
    <UButton color="neutral" variant="outline" :label="t('import')" class="settings-action" :disabled="!importReady || busy" @click="confirmationOpen = true" />
  </SettingsRow>
  <p v-else class="text-sm text-muted">{{ t('noDataActions') }}</p>
  <p v-if="importFeedback" role="status" aria-live="polite" class="text-sm text-muted">{{ importFeedback }}</p>
  <UModal v-model:open="importOpen" :title="t('importTitle')" :description="t('importConfirmation')" :dismissible="!busy" :close="!busy">
    <template #footer>
      <div class="flex w-full flex-wrap justify-end gap-2">
        <UButton color="neutral" variant="ghost" :label="t('cancel')" class="min-h-11" :disabled="busy" @click="importOpen = false" />
        <UButton :label="t('importConfirm')" class="min-h-11" :loading="busy" :disabled="!importReady || busy" @click="importChats" />
      </div>
    </template>
  </UModal>
</template>
