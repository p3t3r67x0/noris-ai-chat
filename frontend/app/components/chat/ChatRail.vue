<script setup lang="ts">
import ProfileMenu from './ProfileMenu.vue'
import { useAppLocale } from '../../composables/useAppLocale'

defineProps<{ demo?: boolean }>()
defineEmits<{ home: [], search: [], archive: [] }>()
const { t } = useAppLocale()
</script>

<template>
  <nav class="chat-rail" aria-label="Noris-Navigation">
    <UTooltip :text="t('home')">
      <UButton color="neutral" variant="ghost" class="rail-home touch-control" :aria-label="t('home')" @click="$emit('home')">
        <span class="rail-mark" aria-hidden="true">n</span>
      </UButton>
    </UTooltip>
    <UTooltip :text="t('searchChats')">
      <UButton icon="i-lucide-search" color="neutral" variant="ghost" class="touch-control" :aria-label="t('searchChats')" @click="$emit('search')" />
    </UTooltip>
    <UTooltip :text="t('archived')">
      <UButton icon="i-lucide-archive" color="neutral" variant="ghost" class="touch-control" :aria-label="t('archived')" @click="$emit('archive')" />
    </UTooltip>
    <div class="flex-1" />
    <ProfileMenu :demo="demo" />
  </nav>
</template>
