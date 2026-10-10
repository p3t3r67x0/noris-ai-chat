<script setup lang="ts">
defineProps<{ title: string, description: string }>()
</script>

<template>
  <section :aria-label="title" class="flex min-w-0 flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
    <div class="min-w-0">
      <h3 class="text-sm font-medium">{{ title }}</h3>
      <p class="mt-1 text-sm text-muted">{{ description }}</p>
    </div>
    <div class="shrink-0"><slot /></div>
  </section>
</template>
