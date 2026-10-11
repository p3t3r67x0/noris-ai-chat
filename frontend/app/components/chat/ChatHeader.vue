<script setup lang="ts">
import { useAppLocale } from '../../composables/useAppLocale'
import type { ChatModelId } from '../../composables/useModelSelection'
import ChatModelMenu from './ChatModelMenu.vue'
const { t } = useAppLocale()

withDefaults(defineProps<{ sidebarOpen: boolean, busy?: boolean, demo?: boolean }>(), { demo: true })
const model = defineModel<ChatModelId>('model', { required: true })
defineEmits<{ toggleSidebar: [], newChat: [] }>()
</script>

<template>
  <header class="chat-header" :aria-label="t('chatControls')">
    <UButton
      icon="i-lucide-panel-left" color="neutral" variant="ghost" class="touch-control"
      :aria-label="sidebarOpen ? t('closeSidebar') : t('openSidebar')" :aria-expanded="sidebarOpen"
      aria-controls="chat-sidebar" @click="$emit('toggleSidebar')"
    />
    <UButton
      v-if="!sidebarOpen" icon="i-lucide-square-pen" color="neutral" variant="ghost"
      class="touch-control" :aria-label="t('newChat')" @click="$emit('newChat')"
    />
    <ChatModelMenu v-model="model" :busy="busy" :label="t('chooseModel')" />
    <div class="flex-1" />
    <span v-if="demo" class="header-demo">{{ t('demo') }}</span>
  </header>
</template>
