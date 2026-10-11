<script setup lang="ts">
import SettingsRow from '../../components/settings/SettingsRow.vue'
import { useAppLocale } from '../../composables/useAppLocale'
const { t } = useAppLocale()
const shortcuts = [
  { keys: 'Enter', action: 'sendMessage' }, { keys: 'Shift + Enter', action: 'newline' },
  { keys: 'Ctrl / ⌘ + K', action: 'chatSearch' }, { keys: 'Ctrl / ⌘ + Shift + O', action: 'newChat' },
  { keys: 'Escape', action: 'stopResponse' },
] as const
</script>

<template>
  <section id="shortcuts" tabindex="-1" :aria-label="t('shortcuts')" class="settings-rows">
    <SettingsRow v-for="shortcut in shortcuts" :key="shortcut.keys" :title="t(shortcut.action)">
      <kbd>{{ shortcut.keys }}</kbd>
    </SettingsRow>
  </section>
</template>
