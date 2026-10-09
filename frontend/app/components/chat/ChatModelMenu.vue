<script setup lang="ts">
import { computed } from 'vue'
import { CHAT_MODELS } from '../../composables/useModelSelection'
import type { ChatModel, ChatModelId } from '../../composables/useModelSelection'

const props = defineProps<{ label: string, busy?: boolean, compact?: boolean }>()
const model = defineModel<ChatModelId>({ required: true })
const items = computed(() => {
  if (!CHAT_MODELS.some(item => item.category)) return [...CHAT_MODELS]
  const groups: { label: string, models: ChatModel[] }[] = [
    { label: 'Automatisch', models: CHAT_MODELS.filter(item => item.virtual) },
    { label: 'Allgemein', models: CHAT_MODELS.filter(item => !item.virtual && item.category !== 'REASONING') },
    { label: 'Reasoning & Entwicklung', models: CHAT_MODELS.filter(item => !item.virtual && item.category === 'REASONING') },
  ]
  return groups.filter(group => group.models.length).flatMap(group => [{ type: 'label' as const, label: group.label, id: `group-${group.label}`, description: '' }, ...group.models])
})
const selected = computed(() => CHAT_MODELS.find(item => item.id === model.value))
const selectedLabel = computed(() => props.compact ? selected.value?.label.replace('noris ', '') : selected.value?.label)
</script>

<template>
  <USelectMenu
    v-model="model" :items="items" value-key="id" :search-input="false" :disabled="busy || !CHAT_MODELS.length"
    variant="ghost" color="neutral" :aria-label="label" :class="compact ? 'composer-model' : 'min-w-0 max-w-64 text-base font-semibold'"
    :ui="{ base: 'min-h-11', content: 'w-80 max-w-[calc(100vw-2rem)]', itemLabel: 'whitespace-normal break-words', itemDescription: 'whitespace-normal', value: 'whitespace-normal break-words' }"
  >
    {{ selectedLabel ?? (model ? 'Modell nicht verfügbar' : 'Modell auswählen') }}
    <template #content-bottom>
      <p class="border-t border-default px-3 py-2 text-xs text-muted">Modellwechsel können unterschiedliche Kosten verursachen.</p>
      <p v-if="CHAT_MODELS.some(item => item.virtual)" class="px-3 pb-2 text-xs text-muted">Bei „Automatisch“ kann das tatsächliche Modell je nach Anfrage wechseln.</p>
    </template>
  </USelectMenu>
</template>
