<script setup lang="ts">
import { de, en } from '@nuxt/ui/locale'
import { provideAppLocale } from './composables/useAppLocale'
const { language } = provideAppLocale()
useHead(() => ({ htmlAttrs: { lang: language.value } }))
</script>

<template>
  <UApp :locale="language === 'de' ? de : en" :toaster="{ position: 'top-right', max: 3, expand: true, progress: false, label: 'Benachrichtigungen', ui: { viewport: 'app-notification-viewport' } }">
    <AppNotificationCenter><NuxtLayout><NuxtPage /></NuxtLayout></AppNotificationCenter>
  </UApp>
</template>
