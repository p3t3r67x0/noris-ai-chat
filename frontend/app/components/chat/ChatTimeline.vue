<script setup lang="ts">
import type { ChatMessage } from '../../lib/chat/types'
import { computed, ref, toRef, watch } from 'vue'
import { useChatScroll } from '../../composables/useChatScroll'
import ChatMessageView from './ChatMessage.vue'

const props = defineProps<{ messages: readonly ChatMessage[], conversationId: string | null, busy: boolean, variants: (id: string) => readonly ChatMessage[], canContinue?: (id: string) => boolean }>()
const emit = defineEmits<{ edit: [id: string], regenerate: [id: string], continue: [id: string], selectVariant: [id: string] }>()
const scroller = ref<HTMLElement | null>(null)
const content = ref<HTMLElement | null>(null)
const turns = computed(() => {
  const result: ChatMessage[][] = []
  for (const message of props.messages) {
    if (message.role === 'user' || result.length === 0) result.push([])
    result.at(-1)?.push(message)
  }
  return result
})
const turnId = computed(() => turns.value.at(-1)?.[0]?.id ?? null)
const scroll = useChatScroll(scroller, content, toRef(props, 'conversationId'), turnId)
watch(() => props.messages.at(-1)?.content, scroll.contentChanged, { flush: 'post' })
</script>

<template>
  <div class="chat-history">
    <div ref="scroller" class="chat-scroll" role="region" aria-label="Nachrichtenverlauf" tabindex="0" @scroll.passive="scroll.onScroll" @wheel.passive="scroll.onWheel" @keydown="scroll.onKeydown" @touchstart.passive="scroll.onTouchstart" @touchmove.passive="scroll.onTouchmove">
      <div ref="content" class="chat-timeline">
        <div v-for="(turn, index) in turns" :key="turn[0]?.id" class="chat-turn" :class="{ 'last-chat-turn': index === turns.length - 1 }">
          <ChatMessageView v-for="message in turn" :key="message.id" :message="message" :busy="busy" :variants="variants(message.id)" :can-continue="canContinue?.(message.id) ?? false" @rendered="scroll.contentRendered" @edit="emit('edit', message.id)" @regenerate="emit('regenerate', message.id)" @continue="emit('continue', message.id)" @select-variant="emit('selectVariant', $event)" />
        </div>
      </div>
    </div>
    <UButton v-if="scroll.showScrollButton.value" icon="i-lucide-arrow-down" color="neutral" variant="outline" class="scroll-to-bottom touch-control rounded-full bg-default shadow-sm" aria-label="Zum Ende scrollen" @click="scroll.scrollToBottom" />
  </div>
</template>
