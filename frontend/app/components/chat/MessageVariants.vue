<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '../../lib/chat/types'

const props = defineProps<{ variants: readonly ChatMessage[], selectedId: string, busy: boolean, role: ChatMessage['role'] }>()
const emit = defineEmits<{ select: [id: string] }>()
const index = computed(() => props.variants.findIndex(message => message.id === props.selectedId))
function select(offset: number): void {
  const variant = props.variants[index.value + offset]
  if (!props.busy && variant) emit('select', variant.id)
}
</script>

<template>
  <div v-if="variants.length > 1" class="message-variants flex items-center" :aria-label="role === 'user' ? 'Fragevarianten' : 'Antwortvarianten'">
    <UButton icon="i-lucide-chevron-left" color="neutral" variant="ghost" class="touch-control" :aria-label="role === 'user' ? 'Vorherige Fragevariante' : 'Vorherige Antwortvariante'" :disabled="busy || index <= 0" @click="select(-1)" />
    <span class="min-w-10 text-center text-xs tabular-nums text-muted" aria-live="polite">{{ index + 1 }} / {{ variants.length }}</span>
    <UButton icon="i-lucide-chevron-right" color="neutral" variant="ghost" class="touch-control" :aria-label="role === 'user' ? 'Nächste Fragevariante' : 'Nächste Antwortvariante'" :disabled="busy || index >= variants.length - 1" @click="select(1)" />
  </div>
</template>
