<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ChatModel } from '../../composables/useModelSelection'
import { REASONING_CHOICES, supportsPreference } from '../../lib/chat/reasoning'
import type { ReasoningPreference } from '../../lib/chat/reasoning'

const props = defineProps<{ model?: ChatModel | undefined, preference?: ReasoningPreference | null | undefined, disabled?: boolean | undefined, anchor?: HTMLElement | null | undefined }>()
const emit = defineEmits<{ select: [preference: ReasoningPreference | null] }>()
const open = ref(false)
const supported = computed(() => props.preference && supportsPreference(props.model, props.preference))
const label = computed(() => supported.value ? REASONING_CHOICES.find(choice => choice.id === props.preference)?.label : 'Standard')
const items = computed(() => [
  ...REASONING_CHOICES.map(choice => ({
    label: choice.label,
    description: supportsPreference(props.model, choice.id) ? choice.description : 'Für dieses Modell nicht verfügbar',
    disabled: props.disabled || !supportsPreference(props.model, choice.id),
    type: 'checkbox' as const,
    checked: Boolean(supported.value && props.preference === choice.id),
    onSelect: () => emit('select', choice.id),
  })),
  { type: 'separator' as const },
  { label: 'Modellstandard', description: 'Voreinstellung des Modells verwenden', type: 'checkbox' as const, checked: !supported.value, disabled: props.disabled, onSelect: () => emit('select', null) },
])
</script>

<template>
  <UDropdownMenu v-model:open="open" :items="items" :content="{ side: 'top', align: 'start', ...(anchor ? { reference: anchor } : {}), sideOffset: 10 }" :ui="{ content: 'composer-floating-menu reasoning-menu', item: 'composer-menu-item', itemWrapper: 'composer-menu-copy', itemLabel: 'composer-menu-title', itemDescription: 'composer-menu-description' }">
    <UButton color="neutral" variant="ghost" trailing-icon="i-lucide-chevron-down" class="composer-reasoning touch-control" :disabled="disabled" :aria-label="`Denkaufwand: ${label}`" :title="label">{{ label }}</UButton>
    <template #content-top>
      <p v-if="preference && !supported" role="status" class="reasoning-notice">Die gespeicherte Denkstufe ist für dieses Modell nicht verfügbar. Der Modellstandard wird verwendet.</p>
    </template>
  </UDropdownMenu>
</template>
