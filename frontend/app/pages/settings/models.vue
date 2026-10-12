<script setup lang="ts">
import { computed } from 'vue'
import { useWorkspace } from '../../composables/useWorkspace'
import { useAppLocale } from '../../composables/useAppLocale'
import SettingsRow from '../../components/settings/SettingsRow.vue'
const { selection, chat, mode } = useWorkspace()
const { t, language } = useAppLocale()
const { modelId, models, catalogModels, loading, error, notice, refresh } = selection
const items = computed(() => models.filter(model => !model.disabled).map(model => ({ label: model.label, value: model.id })))
const tokens = (value?: number) => value ? new Intl.NumberFormat(language.value).format(value) : t('unknown')
</script>

<template>
  <div class="settings-rows">
    <SettingsRow id="default-model" :title="t('defaultModel')" :description="t('defaultModelDescription')">
      <USelect v-model="modelId" :items="items" color="neutral" :aria-label="t('defaultModel')" :disabled="loading || chat.stream.busy.value || !items.length" :placeholder="t('chooseModel')" class="settings-select" :ui="{ base: 'settings-select-trigger', content: 'settings-select-content' }" />
    </SettingsRow>
    <p v-if="mode === 'mock'" class="text-sm text-muted">{{ t('demoModels') }}</p>
    <details v-if="error || notice" class="text-sm text-muted"><summary>Modellzugriff prüfen</summary><p>{{ error || notice }}</p></details>
    <UButton v-if="mode !== 'mock'" color="neutral" variant="outline" :label="t('refreshModels')" :loading="loading" class="settings-action" @click="refresh()" />
    <details v-if="chat.storageWarning.value" class="text-sm text-muted"><summary>Einstellung prüfen</summary><p>{{ chat.storageWarning.value }}</p><UButton v-if="chat.retryPersistence.value" color="neutral" variant="link" label="Erneut speichern" @click="chat.retryPersistence.value?.()" /></details>
    <p v-if="!catalogModels.length && !loading" class="text-muted">{{ t('noModels') }}</p>
    <SettingsRow v-for="model in catalogModels" :id="`model-${model.id}`" :key="model.id" :title="model.label" :description="model.providerDescription ?? model.description">
      <template #details>
        <dl class="settings-model-details">
          <div><dt>{{ t('context') }}</dt><dd>{{ tokens(model.contextWindow) }}</dd></div>
          <div><dt>{{ t('outputLimit') }}</dt><dd>{{ tokens(model.effectiveOutputLimit) }}</dd></div>
        </dl>
      </template>
      <span class="settings-model-status">{{ model.disabled ? t('unavailable') : t('available') }}</span>
    </SettingsRow>
  </div>
</template>
