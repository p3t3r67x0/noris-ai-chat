<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useChat } from '../../composables/useChat'
import { createMockTransport } from '../../lib/chat/mockTransport'
import { useModelSelection } from '../../composables/useModelSelection'
import ChatHeader from './ChatHeader.vue'
import ChatSidebar from './ChatSidebar.vue'
import EmptyChatState from './EmptyChatState.vue'
import ChatComposer from './ChatComposer.vue'
import ChatTimeline from './ChatTimeline.vue'

const chat = useChat(createMockTransport())
const { conversations, stream } = chat
const { modelId } = useModelSelection()
const draft = ref('')
const sidebarOpen = ref(true)
const ready = ref(false)
onMounted(() => { ready.value = true })

function send(text: string): void {
  if (chat.send(text, modelId.value)) draft.value = ''
}
</script>

<template>
  <div class="chat-workspace" :data-ready="ready" :inert="!ready" :aria-busy="!ready">
    <a href="#chat-main" class="sr-only z-50 rounded-md bg-default p-3 focus:not-sr-only focus:fixed focus:left-4 focus:top-4">Zum Chat springen</a>
    <ChatSidebar
      v-model:open="sidebarOpen" :conversations="conversations.visible.value" :archived="conversations.archived.value"
      :active-id="conversations.activeId.value"
      @new-chat="chat.newChat" @select="conversations.select" @rename="conversations.rename"
      @archive="conversations.archive" @restore="conversations.restore" @delete="chat.remove"
    />
    <main id="chat-main" class="chat-main" aria-label="Chat" tabindex="-1">
      <ChatHeader v-model:model="modelId" :sidebar-open="sidebarOpen" :busy="stream.busy.value" @toggle-sidebar="sidebarOpen = !sidebarOpen" @new-chat="chat.newChat" />
      <div class="chat-content">
        <EmptyChatState v-if="chat.visible.value.length === 0">
          <ChatComposer v-model="draft" v-model:model="modelId" :busy="stream.busy.value" :streaming="stream.status.value === 'streaming'" :cancellation-requested="stream.cancellationRequested.value" @send="send" @stop="stream.stop" />
        </EmptyChatState>
        <template v-else>
          <ChatTimeline :messages="chat.visible.value" />
          <div class="composer-dock">
            <ChatComposer v-model="draft" v-model:model="modelId" :busy="stream.busy.value" :streaming="stream.status.value === 'streaming'" :cancellation-requested="stream.cancellationRequested.value" @send="send" @stop="stream.stop" />
            <p class="mt-2 text-center text-[11px] text-muted">noris AI kann Fehler machen. Prüfe wichtige Informationen.</p>
          </div>
        </template>
        <div class="chat-status" role="status" aria-live="polite" aria-atomic="true" :data-generation-status="stream.status.value">
          <span v-if="stream.status.value === 'submitting'">Antwort wird vorbereitet …</span>
          <span v-else-if="stream.status.value === 'streaming'">{{ stream.cancellationRequested.value ? 'Antwort wird gestoppt …' : 'noris AI antwortet …' }}</span>
          <span v-else-if="stream.status.value === 'cancelled'">Antwort gestoppt.</span>
          <template v-else-if="stream.status.value === 'failed'">
            <span>{{ stream.error.value }}</span>
            <UButton color="neutral" variant="ghost" label="Erneut versuchen" class="min-h-11" :disabled="stream.busy.value" @click="chat.retry(modelId)" />
          </template>
          <span v-else-if="stream.status.value === 'completed'" class="sr-only">Antwort abgeschlossen.</span>
        </div>
        <p v-if="chat.storageWarning.value" role="alert" class="px-4 pb-3 text-center text-xs text-warning">{{ chat.storageWarning.value }}</p>
      </div>
    </main>
  </div>
</template>
