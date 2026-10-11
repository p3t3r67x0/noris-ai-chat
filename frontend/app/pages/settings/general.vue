<script setup lang="ts">
import SettingsRow from '../../components/settings/SettingsRow.vue'
import { useAppLocale } from '../../composables/useAppLocale'
const { preference, t, storageError } = useAppLocale()
</script>

<template>
  <div class="settings-rows">
    <SettingsRow id="language" :title="t('language')" :description="t('languageDescription')">
      <USelect v-model="preference" :items="[{ label: t('automatic'), value: 'auto' }, { label: 'Deutsch', value: 'de' }, { label: 'English', value: 'en' }]" color="neutral" :aria-label="t('language')" class="settings-select" :ui="{ base: 'settings-select-trigger', content: 'settings-select-content' }" />
    </SettingsRow>
    <p v-if="storageError" role="status" class="text-sm text-muted">{{ t('language') }}: {{ t('unavailable') }}</p>
  </div>
</template>
