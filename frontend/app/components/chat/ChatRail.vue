<script setup lang="ts">
import ProfileMenu from './ProfileMenu.vue'
import { useAppLocale } from '../../composables/useAppLocale'

defineProps<{ demo?: boolean, homeActive?: boolean, archiveActive?: boolean, sidebarOpen?: boolean | undefined }>()
defineEmits<{ home: [], search: [], archive: [], openSidebar: [] }>()
const { t } = useAppLocale()
</script>

<template>
  <nav class="chat-rail" aria-label="Noris-Navigation">
    <UTooltip v-if="sidebarOpen === false" :text="t('openSidebar')">
      <UButton icon="i-lucide-panel-left-open" color="neutral" variant="ghost" class="touch-control rail-sidebar-open" :aria-label="t('openSidebar')" aria-controls="chat-sidebar" :aria-expanded="false" @click="$emit('openSidebar')" />
    </UTooltip>
    <UTooltip v-else :text="t('home')">
      <UButton icon="i-lucide-house" color="neutral" variant="ghost" class="rail-home touch-control" :aria-label="t('home')" :aria-current="homeActive ? 'page' : undefined" @click="$emit('home')" />
    </UTooltip>
    <UTooltip :text="t('searchChats')">
      <UButton icon="i-lucide-search" color="neutral" variant="ghost" class="touch-control" :aria-label="t('searchChats')" @click="$emit('search')" />
    </UTooltip>
    <UTooltip :text="t('archived')">
      <UButton icon="i-lucide-archive" color="neutral" variant="ghost" class="touch-control" :aria-label="t('archived')" :aria-current="archiveActive ? 'page' : undefined" @click="$emit('archive')" />
    </UTooltip>
    <div class="flex-1" />
    <ProfileMenu :demo="demo" />
  </nav>
</template>
