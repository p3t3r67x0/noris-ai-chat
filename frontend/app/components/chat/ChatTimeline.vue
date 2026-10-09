<script setup lang="ts">
import type { ChatMessage } from '../../lib/chat/types'
import ChatMessageView from './ChatMessage.vue'

defineProps<{ messages: readonly ChatMessage[] }>()
</script>

<template>
  <div class="chat-scroll" role="region" aria-label="Nachrichtenverlauf" tabindex="0">
    <div class="chat-timeline">
      <ChatMessageView v-for="message in messages" :key="message.id" :message="message" />
    </div>
  </div>
</template>
