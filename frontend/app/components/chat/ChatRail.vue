<script setup lang="ts">
import { ref } from 'vue'

defineEmits<{ home: [], search: [], archive: [] }>()
const accountOpen = ref(false)
</script>

<template>
  <nav class="chat-rail" aria-label="Noris-Navigation">
    <UTooltip text="Noris Home">
      <UButton color="neutral" variant="ghost" class="rail-home touch-control" aria-label="Noris Home – neuer Chat" @click="$emit('home')">
        <span class="rail-mark" aria-hidden="true">n</span>
      </UButton>
    </UTooltip>
    <UTooltip text="Chats suchen">
      <UButton icon="i-lucide-search" color="neutral" variant="ghost" class="touch-control" aria-label="Chats suchen" @click="$emit('search')" />
    </UTooltip>
    <UTooltip text="Archivierte Chats">
      <UButton icon="i-lucide-archive" color="neutral" variant="ghost" class="touch-control" aria-label="Archivierte Chats" @click="$emit('archive')" />
    </UTooltip>
    <div class="flex-1" />
    <UPopover v-model:open="accountOpen" :content="{ side: 'right', align: 'end' }">
      <UButton color="neutral" variant="ghost" class="touch-control rounded-full" aria-label="Lokaler Arbeitsbereich">
        <UAvatar text="N" size="sm" />
      </UButton>
      <template #content>
        <div class="w-64 space-y-3 p-4">
          <p class="text-sm font-medium">Noris AI Chat</p>
          <p class="text-xs text-muted">Lokale Demo · Anmeldung noch nicht verfügbar</p>
          <UColorModeSelect aria-label="Darstellung im Kontomenü" class="w-full" :ui="{ base: 'min-h-11' }" />
        </div>
      </template>
    </UPopover>
  </nav>
</template>
