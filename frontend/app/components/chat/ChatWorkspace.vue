<script setup lang="ts">
import { ref } from 'vue'
import { useConversations } from '../../composables/useConversations'
import { useModelSelection } from '../../composables/useModelSelection'
import ChatHeader from './ChatHeader.vue'
import ChatSidebar from './ChatSidebar.vue'
import EmptyChatState from './EmptyChatState.vue'

const conversations = useConversations()
const { modelId } = useModelSelection()
const sidebarOpen = ref(true)
</script>

<template>
  <div class="chat-workspace">
    <a href="#chat-main" class="sr-only z-50 rounded-md bg-default p-3 focus:not-sr-only focus:fixed focus:left-4 focus:top-4">Zum Chat springen</a>
    <ChatSidebar
      v-model:open="sidebarOpen" :conversations="conversations.visible.value" :archived="conversations.archived.value"
      :active-id="conversations.activeId.value"
      @new-chat="conversations.create()" @select="conversations.select" @rename="conversations.rename"
      @archive="conversations.archive" @restore="conversations.restore" @delete="conversations.remove"
    />
    <main id="chat-main" class="chat-main" aria-label="Chat" tabindex="-1">
      <ChatHeader v-model:model="modelId" :sidebar-open="sidebarOpen" @toggle-sidebar="sidebarOpen = !sidebarOpen" @new-chat="conversations.create()" />
      <div class="chat-content">
        <EmptyChatState />
        <p v-if="conversations.storageWarning.value" role="alert" class="px-4 pb-3 text-center text-xs text-warning">{{ conversations.storageWarning.value }}</p>
      </div>
    </main>
  </div>
</template>
