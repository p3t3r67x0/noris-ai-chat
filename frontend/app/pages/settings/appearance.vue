<script setup lang="ts">
import { computed } from 'vue'
import SettingsRow from '../../components/settings/SettingsRow.vue'
import { useAppLocale } from '../../composables/useAppLocale'
const { t } = useAppLocale()
const colorMode = useColorMode()
const preference = computed({ get: () => colorMode.preference, set: (value: string) => { colorMode.preference = value } })
</script>

<template>
  <SettingsRow id="theme" :title="t('appearance')" :description="t('themeDescription')">
    <USelect v-model="preference" :items="[{ label: t('system'), value: 'system' }, { label: t('light'), value: 'light' }, { label: t('dark'), value: 'dark' }]" color="neutral" :aria-label="`${t('appearance')} ${t('settings')}`" class="settings-select" :ui="{ base: 'settings-select-trigger', content: 'settings-select-content' }" />
  </SettingsRow>
</template>
