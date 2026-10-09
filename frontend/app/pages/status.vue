<script setup lang="ts">
const { status, refresh } = useServiceHealth()
useHead({ title: 'noris AI — Dienststatus' })
</script>

<template>
  <main class="status-page">
    <h1>noris AI</h1>
    <p>Dienststatus und Verbindung zur Datenbank.</p>
    <ServiceStatus :status="status" @retry="refresh" />
    <NuxtLink to="/" class="mt-6 inline-block text-primary underline">Zum Chat</NuxtLink>
  </main>
</template>
