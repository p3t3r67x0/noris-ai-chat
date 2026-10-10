<script setup lang="ts">
import type { ApiSchemas } from '../../types/generated/api'
import { computed } from 'vue'
import type { ChatMessage } from '../../lib/chat/types'

const props = defineProps<{ variants: readonly ChatMessage[], selectedId: string, busy: boolean, role: ChatMessage['role'], summary?: ApiSchemas['VariantSummary'] | undefined }>()
const emit = defineEmits<{ select: [id: string] }>()
const index = computed(() => props.summary ? props.summary.index - 1 : props.variants.findIndex(message => message.id === props.selectedId))
const total = computed(() => props.summary?.total ?? props.variants.length)
function select(offset: number): void {
  const id = props.summary ? (offset < 0 ? props.summary.previousMessageId : props.summary.nextMessageId) : props.variants[index.value + offset]?.id
  if (!props.busy && id) emit('select', id)
}
</script>

<template>
  <div v-if="total > 1" class="message-variants flex items-center" :aria-label="role === 'user' ? 'Fragevarianten' : 'Antwortvarianten'">
    <UButton icon="i-lucide-chevron-left" color="neutral" variant="ghost" class="touch-control" :aria-label="role === 'user' ? 'Vorherige Fragevariante' : 'Vorherige Antwortvariante'" :disabled="busy || index <= 0" @click="select(-1)" />
    <span class="min-w-10 text-center text-xs tabular-nums text-muted" aria-live="polite">{{ index + 1 }} / {{ total }}</span>
    <UButton icon="i-lucide-chevron-right" color="neutral" variant="ghost" class="touch-control" :aria-label="role === 'user' ? 'Nächste Fragevariante' : 'Nächste Antwortvariante'" :disabled="busy || index >= total - 1" @click="select(1)" />
  </div>
</template>
