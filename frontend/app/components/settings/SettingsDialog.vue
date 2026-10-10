<script setup lang="ts">
import { computed, ref } from 'vue'
import SettingsRow from './SettingsRow.vue'

const props = defineProps<{ importAvailable: boolean, importReady: boolean, importBusy: boolean, importLocalChats: () => Promise<void>, importFeedback: string | null }>()
const open = defineModel<boolean>('open', { required: true })
const pending = ref(false)
const busy = computed(() => props.importBusy || pending.value)
const settingsOpen = computed({ get: () => open.value, set: (value: boolean) => { if (!busy.value) open.value = value } })
const confirmationOpen = ref(false)
const importOpen = computed({ get: () => confirmationOpen.value, set: (value: boolean) => { if (!busy.value) confirmationOpen.value = value } })
const tabs = [
  { label: 'Allgemein', value: 'general', slot: 'general' },
  { label: 'Datenkontrollen', value: 'data-controls', slot: 'data-controls' },
]

async function importChats(): Promise<void> {
  if (!confirmationOpen.value || busy.value || !props.importAvailable || !props.importReady) return
  pending.value = true
  try { await props.importLocalChats() }
  finally { pending.value = false; confirmationOpen.value = false }
}
</script>

<template>
  <UModal v-model:open="settingsOpen" title="Einstellungen" description="Darstellung und Datenkontrollen für deinen Arbeitsbereich." :dismissible="!busy" :close="!busy" :ui="{ content: 'max-w-xl' }">
    <template #body>
      <UTabs :items="tabs" default-value="general" class="w-full" :ui="{ trigger: 'min-h-11' }">
        <template #general>
          <SettingsRow title="Darstellung" description="Wähle das Erscheinungsbild von noris AI.">
            <UColorModeSelect aria-label="Darstellung in den Einstellungen" :ui="{ base: 'min-h-11' }" />
          </SettingsRow>
        </template>
        <template #data-controls>
          <SettingsRow v-if="importAvailable" title="Lokale Chats importieren" description="Übertrage bisher lokal gespeicherte Unterhaltungen in die PostgreSQL-Datenbank.">
            <UButton color="neutral" variant="outline" label="Importieren" class="min-h-11" :disabled="!importReady || busy" @click="confirmationOpen = true" />
          </SettingsRow>
          <p v-else class="py-4 text-sm text-muted">Hier sind derzeit keine Datenaktionen verfügbar.</p>
          <p v-if="importFeedback" role="status" aria-live="polite" class="pt-2 text-sm text-muted">{{ importFeedback }}</p>
        </template>
      </UTabs>
    </template>
  </UModal>
  <UModal v-model:open="importOpen" title="Lokale Chats importieren" description="Überträgt die bisherigen Browser-Chats einschließlich Varianten, Titeln und Entwürfen in die Datenbank. Die lokale Sicherung bleibt erhalten. Bei Konflikten wird der Import abgebrochen." :dismissible="!busy" :close="!busy">
    <template #footer>
      <div class="flex w-full flex-wrap justify-end gap-2">
        <UButton color="neutral" variant="ghost" label="Abbrechen" class="min-h-11" :disabled="busy" @click="importOpen = false" />
        <UButton label="Import ausdrücklich starten" class="min-h-11" :loading="busy" :disabled="!importReady || busy" @click="importChats" />
      </div>
    </template>
  </UModal>
</template>
