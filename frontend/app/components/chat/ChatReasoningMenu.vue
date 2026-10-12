<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ChatModel } from '../../composables/useModelSelection'
import { REASONING_CHOICES, reasoningChoices, supportsPreference } from '../../lib/chat/reasoning'
import type { ReasoningPreference } from '../../lib/chat/reasoning'

const props = defineProps<{ model?: ChatModel | undefined, preference?: ReasoningPreference | null | undefined, disabled?: boolean | undefined, anchor?: HTMLElement | null | undefined }>()
const emit = defineEmits<{ select: [preference: ReasoningPreference | null] }>()
const open = ref(false)
const supported = computed(() => props.preference && supportsPreference(props.model, props.preference))
const label = computed(() => supported.value ? REASONING_CHOICES.find(choice => choice.id === props.preference)?.label : 'Standard')
const items = computed(() => [
  ...reasoningChoices(props.model).map(choice => ({
    label: choice.label,
    description: choice.description,
    disabled: props.disabled,
    type: 'checkbox' as const,
    checked: Boolean(supported.value && props.preference === choice.id),
    onSelect: () => emit('select', choice.id),
  })),
  { type: 'separator' as const },
  { label: 'Modellstandard', description: 'Voreinstellung des Modells verwenden', type: 'checkbox' as const, checked: !supported.value, disabled: props.disabled, onSelect: () => emit('select', null) },
])
</script>

<template>
  <UDropdownMenu v-if="reasoningChoices(model).length" v-model:open="open" :items="items" :content="{ side: 'top', align: 'start', ...(anchor ? { reference: anchor } : {}), sideOffset: 10, collisionPadding: 12, loop: true }" :ui="{ content: 'composer-floating-menu reasoning-menu', item: 'composer-menu-item', itemWrapper: 'composer-menu-copy', itemLabel: 'composer-menu-title whitespace-nowrap', itemDescription: 'composer-menu-description', itemTrailingIcon: 'shrink-0' }">
    <UButton color="neutral" variant="ghost" trailing-icon="i-lucide-chevron-down" class="composer-reasoning touch-control inline-flex shrink-0 items-center whitespace-nowrap" :ui="{ trailingIcon: 'shrink-0' }" :disabled="disabled" :aria-label="`Denkaufwand: ${label}`" :title="label"><span class="whitespace-nowrap">{{ label }}</span></UButton>
  </UDropdownMenu>
</template>
