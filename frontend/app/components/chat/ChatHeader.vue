<script setup lang="ts">
import type { ChatModelId } from '../../composables/useModelSelection'
import ChatModelMenu from './ChatModelMenu.vue'

withDefaults(defineProps<{ sidebarOpen: boolean, busy?: boolean, demo?: boolean }>(), { demo: true })
const model = defineModel<ChatModelId>('model', { required: true })
defineEmits<{ toggleSidebar: [], newChat: [] }>()
</script>

<template>
  <header class="chat-header" aria-label="Chat-Steuerung">
    <UButton
      icon="i-lucide-panel-left" color="neutral" variant="ghost" class="touch-control"
      :aria-label="sidebarOpen ? 'Sidebar schließen' : 'Sidebar öffnen'" :aria-expanded="sidebarOpen"
      aria-controls="chat-sidebar" @click="$emit('toggleSidebar')"
    />
    <UButton
      v-if="!sidebarOpen" icon="i-lucide-square-pen" color="neutral" variant="ghost"
      class="touch-control" aria-label="Neuer Chat" @click="$emit('newChat')"
    />
    <ChatModelMenu v-model="model" :busy="busy" label="Modell auswählen" />
    <div class="flex-1" />
    <span v-if="demo" class="header-demo">Lokale Demo</span>
  </header>
</template>
