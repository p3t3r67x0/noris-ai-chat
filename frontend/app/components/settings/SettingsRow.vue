<script setup lang="ts">
defineProps<{ title: string, description?: string }>()
</script>

<template>
  <section :aria-label="title" class="settings-row" tabindex="-1">
    <div class="settings-row-copy">
      <h2>{{ title }}</h2>
      <p v-if="description">{{ description }}</p>
      <slot name="details" />
    </div>
    <div v-if="$slots.default" class="settings-row-action"><slot /></div>
  </section>
</template>
