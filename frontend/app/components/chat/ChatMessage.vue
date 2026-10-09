<script setup lang="ts">
import type { ChatMessage } from '../../lib/chat/types'
import { useCopy } from '../../composables/useCopy'
import MarkdownContent from './MarkdownContent'
import MessageVariants from './MessageVariants.vue'

withDefaults(defineProps<{ message: ChatMessage, variants?: readonly ChatMessage[], busy?: boolean }>(), { variants: () => [], busy: false })
const emit = defineEmits<{ edit: [], regenerate: [], selectVariant: [id: string] }>()
const { copy, copied, copyError } = useCopy()
</script>

<template>
  <article :class="['chat-message', `message-${message.role}`]" :data-message-id="message.id" :data-status="message.status" :aria-label="message.role === 'user' ? 'Deine Nachricht' : 'Antwort von noris AI'">
    <p v-if="message.role === 'user'" class="user-bubble">{{ message.content }}</p>
    <div v-else class="assistant-content">
      <MarkdownContent v-if="message.content" :content="message.content" />
      <div v-else-if="message.status === 'submitting' || message.status === 'streaming'" class="thinking-dot" aria-hidden="true" />
      <p v-if="message.status === 'cancelled'" class="mt-3 text-xs text-muted">Antwort gestoppt · unvollständig</p>
      <p v-else-if="message.status === 'failed'" class="mt-3 text-xs text-error">Antwort nicht abgeschlossen</p>
    </div>
    <div v-if="message.content && message.status !== 'streaming' && message.status !== 'submitting'" class="message-actions">
      <UButton :icon="copied ? 'i-lucide-check' : 'i-lucide-copy'" color="neutral" variant="ghost" class="touch-control" :aria-label="copied ? 'Nachricht kopiert' : 'Nachricht kopieren'" @click="copy(message.content)" />
      <UButton v-if="message.role === 'user'" icon="i-lucide-pencil" color="neutral" variant="ghost" class="touch-control" aria-label="Nachricht bearbeiten" :disabled="busy" @click="emit('edit')" />
      <UButton v-else icon="i-lucide-rotate-ccw" color="neutral" variant="ghost" class="touch-control" aria-label="Antwort erneut generieren" :disabled="busy" @click="emit('regenerate')" />
      <MessageVariants :variants="variants" :selected-id="message.id" :busy="busy" :role="message.role" @select="emit('selectVariant', $event)" />
    </div>
    <p v-if="copyError" role="status" class="text-xs text-error">{{ copyError }}</p>
  </article>
</template>
