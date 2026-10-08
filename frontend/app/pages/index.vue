<script setup lang="ts">
const { status, refresh } = useServiceHealth()
</script>

<template>
  <main>
    <h1>noris AI</h1>
    <p>Die Anwendung wird vorbereitet.</p>
    <ServiceStatus :status="status" @retry="refresh" />
  </main>
</template>
