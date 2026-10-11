<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { settingsRegistry, searchSettings } from '../../lib/settings/registry'
import { useAppLocale } from '../../composables/useAppLocale'
import { useWorkspace } from '../../composables/useWorkspace'

const { t, language } = useAppLocale()
const { selection, importAvailable } = useWorkspace()
const route = useRoute()
const router = useRouter()
const expanded = ref(false)
const query = ref('')
const results = computed(() => searchSettings(query.value, language.value, { importAvailable: importAvailable.value, models: selection.catalogModels.value }))
const active = computed(() => settingsRegistry.find(category => route.path === `/settings/${category.id}`))
watch(() => route.fullPath, () => { query.value = ''; expanded.value = false })
function firstResult(): void { if (results.value[0]) void router.push(results.value[0].to) }
</script>

<template>
  <aside class="settings-sidebar" :data-expanded="expanded" :aria-label="t('settings')">
    <div class="settings-sidebar-heading">
      <h2>{{ t('settings') }}</h2>
      <UButton icon="i-lucide-chevron-down" color="neutral" variant="ghost" class="settings-mobile-toggle touch-control" :label="active ? t(active.title) : t('general')" :aria-label="t('settingsNavigation')" :aria-expanded="expanded" aria-controls="settings-navigation" @click="expanded = !expanded" />
    </div>
    <div id="settings-navigation" class="settings-sidebar-body">
      <UInput v-model="query" icon="i-lucide-search" :placeholder="t('search')" :aria-label="t('settingsSearch')" autocomplete="off" class="settings-search" :ui="{ base: 'settings-search-input', leadingIcon: 'size-5' }" @keydown.enter.prevent="firstResult" @keydown.esc.stop="query = ''" />
      <nav :aria-label="t('settingsNavigation')">
        <template v-if="query.trim()">
          <p role="status" class="settings-group">{{ results.length ? `${results.length}` : t('noResults') }}</p>
          <ul>
            <li v-for="result in results" :key="result.key">
              <NuxtLink :to="result.to" class="settings-nav-link settings-search-result">
                <span>{{ result.label }}<small>{{ result.category }}</small></span>
                <UIcon name="i-lucide-chevron-right" />
              </NuxtLink>
            </li>
          </ul>
        </template>
        <template v-else>
          <section v-for="group in ['personal', 'noris'] as const" :key="group" :aria-label="group === 'personal' ? t('personal') : 'Noris AI'">
            <h3 class="settings-group">{{ group === 'personal' ? t('personal') : 'Noris AI' }}</h3>
            <ul>
              <li v-for="category in settingsRegistry.filter(item => item.group === group)" :key="category.id">
                <NuxtLink :to="`/settings/${category.id}`" class="settings-nav-link" :aria-current="active?.id === category.id ? 'page' : undefined">
                  <UIcon :name="category.icon" /><span>{{ t(category.title) }}</span>
                </NuxtLink>
              </li>
            </ul>
          </section>
        </template>
      </nav>
      <NuxtLink to="/" class="settings-nav-link settings-back"><UIcon name="i-lucide-arrow-left" />{{ t('backChat') }}</NuxtLink>
    </div>
  </aside>
</template>
