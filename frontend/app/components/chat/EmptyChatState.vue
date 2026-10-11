<script setup lang="ts">
import { useAppLocale } from '../../composables/useAppLocale'
const { t } = useAppLocale()
</script>
<template>
  <section class="empty-chat" aria-labelledby="welcome-title">
    <h1 id="welcome-title">{{ t('welcome') }}</h1>
  </section>
</template>
