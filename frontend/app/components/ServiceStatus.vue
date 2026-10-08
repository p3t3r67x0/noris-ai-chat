<script setup lang="ts">
import type { ServiceHealth } from '../composables/useServiceHealth'

defineProps<{ status: ServiceHealth }>()
defineEmits<{ retry: [] }>()

const labels: Record<ServiceHealth, string> = {
  checking: 'Verbindung wird geprüft …',
  healthy: 'Dienst verfügbar',
  unavailable: 'Dienst derzeit nicht erreichbar',
}
</script>

<template>
  <div class="service-status">
    <p role="status">{{ labels[status] }}</p>
    <button type="button" :disabled="status === 'checking'" @click="$emit('retry')">
      Verbindung prüfen
    </button>
  </div>
</template>
