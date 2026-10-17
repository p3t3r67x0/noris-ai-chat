<script setup lang="ts">
import { useId } from 'vue'

defineProps<{ title: string, collapsible?: boolean }>()
const open = defineModel<boolean>('open', { default: true })
// USidebar reuses its content slot for desktop and drawer. Each rendered
// section needs its own ARIA target, even though both share the open preference.
const contentId = useId()
</script>

<template>
  <section class="sidebar-section" :aria-label="title">
    <h2 class="sidebar-group">
      <button v-if="collapsible" type="button" class="sidebar-section-toggle" :aria-expanded="open" :aria-controls="contentId" @click="open = !open">
        {{ title }}
        <UIcon :name="open ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'" class="size-4" aria-hidden="true" />
      </button>
      <template v-else>{{ title }}</template>
    </h2>
    <div v-show="!collapsible || open" :id="contentId"><slot /></div>
  </section>
</template>
