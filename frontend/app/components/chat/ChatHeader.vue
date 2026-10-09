<script setup lang="ts">
import type { ChatModelId } from '../../composables/useModelSelection'
import { CHAT_MODELS } from '../../composables/useModelSelection'

defineProps<{ sidebarOpen: boolean, busy?: boolean }>()
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
    <USelectMenu
      v-model="model" :items="[...CHAT_MODELS]" value-key="id" :search-input="false" :disabled="busy"
      variant="ghost" color="neutral" aria-label="Modell auswählen" class="min-w-0 max-w-56 text-base font-semibold"
      :ui="{ base: 'min-h-11', content: 'min-w-64' }"
    >
      <template #item-label="{ item }">
        <span class="block">{{ item.label }}<span class="block text-xs font-normal text-muted">{{ item.description }}</span></span>
      </template>
    </USelectMenu>
    <span class="hidden rounded-full border border-default px-2 py-0.5 text-[11px] text-muted sm:inline">Demo</span>
    <div class="flex-1" />
    <UButton disabled color="neutral" variant="ghost" class="touch-control" aria-label="Profil – lokale Demo">
      <UAvatar text="N" size="sm" />
    </UButton>
  </header>
</template>
