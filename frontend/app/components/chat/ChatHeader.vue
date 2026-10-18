<script setup lang="ts">
import { useAppLocale } from '../../composables/useAppLocale'
const { t } = useAppLocale()

withDefaults(defineProps<{ sidebarOpen: boolean, demo?: boolean }>(), { demo: true })
defineEmits<{ toggleSidebar: [], newChat: [] }>()
</script>

<template>
  <header class="chat-header" :aria-label="t('chatControls')">
    <UButton
      icon="i-lucide-panel-left" color="neutral" variant="ghost" class="noris-nav-icon-button"
      :aria-label="sidebarOpen ? t('closeSidebar') : t('openSidebar')" :aria-expanded="sidebarOpen"
      aria-controls="chat-sidebar" @click="$emit('toggleSidebar')"
    />
    <UButton
      v-if="!sidebarOpen" icon="i-lucide-square-pen" color="neutral" variant="ghost"
      class="noris-nav-icon-button" :aria-label="t('newChat')" @click="$emit('newChat')"
    />
    <div class="flex-1" />
    <span v-if="demo" class="header-demo">{{ t('demo') }}</span>
  </header>
</template>
