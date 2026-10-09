<script setup lang="ts">
import type { ChatMessage } from '../../lib/chat/types'
import ChatMessageView from './ChatMessage.vue'

defineProps<{ messages: readonly ChatMessage[], busy: boolean, variants: (id: string) => readonly ChatMessage[] }>()
const emit = defineEmits<{ edit: [id: string], regenerate: [id: string], selectVariant: [id: string] }>()
</script>

<template>
  <div class="chat-scroll" role="region" aria-label="Nachrichtenverlauf" tabindex="0">
    <div class="chat-timeline">
      <ChatMessageView v-for="message in messages" :key="message.id" :message="message" :busy="busy" :variants="variants(message.id)" @edit="emit('edit', message.id)" @regenerate="emit('regenerate', message.id)" @select-variant="emit('selectVariant', $event)" />
    </div>
  </div>
</template>
