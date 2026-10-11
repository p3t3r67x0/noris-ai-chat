<script setup lang="ts">
import { computed, nextTick, watch } from 'vue'
import SettingsSidebar from '../components/settings/SettingsSidebar.vue'
import { settingsRegistry } from '../lib/settings/registry'
import { useAppLocale } from '../composables/useAppLocale'
const route = useRoute()
const { t } = useAppLocale()
const category = computed(() => settingsRegistry.find(item => route.path === `/settings/${item.id}`))
useHead(() => ({ title: `noris AI — ${category.value ? t(category.value.title) : t('settings')}` }))
async function focusSetting(): Promise<void> {
  await nextTick()
  if (!import.meta.client) return
  let id = ''
  try { id = decodeURIComponent(route.hash.slice(1)) }
  catch { /* An invalid fragment falls back to the page heading. */ }
  const row = id ? document.getElementById(id) : null
  const target = row?.querySelector<HTMLElement>('button:not(:disabled), input, a[href]') ?? row ?? document.getElementById('settings-heading')
  target?.scrollIntoView({ block: 'nearest' })
  target?.focus({ preventScroll: true })
}
watch(() => route.fullPath, focusSetting, { immediate: true, flush: 'post' })
</script>

<template>
  <div class="settings-layout">
    <SettingsSidebar />
    <main id="settings-main" class="settings-main" :aria-label="t('settings')" tabindex="-1">
      <div class="settings-content">
        <h1 id="settings-heading" tabindex="-1">{{ category ? t(category.title) : t('settings') }}</h1>
        <div class="settings-rows"><NuxtPage /></div>
      </div>
    </main>
  </div>
</template>
