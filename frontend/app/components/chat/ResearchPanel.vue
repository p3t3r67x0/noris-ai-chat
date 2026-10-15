<script setup lang="ts">
import { computed, nextTick, ref, shallowRef } from 'vue'
import { useAppLocale } from '../../composables/useAppLocale'
import { researchErrorKey, researchStates, sourceDomain, sourceHref } from '../../lib/chat/research'
import type { ResearchView } from '../../lib/chat/types'

const props = defineProps<{ research: ResearchView, errorCode?: string | undefined, loadFailed?: boolean | undefined }>()
const { t, language } = useAppLocale()
const returnFocus = shallowRef<HTMLElement | null>(null)
const selectedId = ref<string | null>(null)
const selected = computed(() => props.research.sources.find(source => source.sourceId === selectedId.value))
const open = computed({ get: () => Boolean(selected.value), set: (value: boolean) => { if (!value) selectedId.value = null } })
const status = computed(() => t(props.research.state === 'failed' ? researchErrorKey(props.errorCode) : researchStates[props.research.state]))
function openSource(id: string, event?: MouseEvent): void { returnFocus.value = event?.currentTarget instanceof HTMLElement ? event.currentTarget : document.activeElement instanceof HTMLElement ? document.activeElement : null; selectedId.value = id }
function restoreFocus(event: Event): void { event.preventDefault(); void nextTick(() => { if (returnFocus.value?.isConnected) returnFocus.value.focus({ preventScroll: true }) }) }
function openCitation(marker: string, event?: MouseEvent): void {
  const source = props.research.sources.find(source => source.marker === marker && source.status === 'context_prepared')
  if (source) openSource(source.sourceId, event)
}
function reload(): void { window.location.reload() }
function fetchedAt(value: string): string { return new Date(value).toLocaleString(language.value) }
defineExpose({ openCitation })
</script>

<template>
  <section class="research-panel" :aria-label="t('webSearch')" :data-research-state="research.state">
    <p role="status" aria-live="polite" aria-atomic="true" class="research-status"><UIcon name="i-lucide-globe" aria-hidden="true" class="size-4 shrink-0" />{{ status }}</p>
    <div v-if="loadFailed" role="status" class="text-xs text-muted">{{ t('researchLoadFailed') }} <UButton :label="t('retry')" variant="link" color="neutral" @click="reload" /></div>
    <p v-if="research.inherited" class="text-xs text-muted">{{ t('researchInherited') }}</p>
    <template v-if="research.sources.length">
      <p class="mt-2 text-sm font-medium">{{ t('researchSources') }}</p>
      <ul class="research-sources">
        <li v-for="source in research.sources" :key="source.sourceId">
          <button type="button" class="research-source" :aria-label="`${t('researchOpenSource')}: ${source.title}`" @click="openSource(source.sourceId, $event)">
            <span v-if="source.marker" class="research-number">{{ source.marker.slice(1) }}</span>
            <span class="min-w-0"><span class="block font-medium">{{ source.title }}</span><span class="block text-xs text-muted">{{ sourceDomain(source.originalUrl) }} · {{ t(source.status === 'unavailable' ? 'researchSourceUnavailable' : 'researchPrepared') }}</span></span>
          </button>
        </li>
      </ul>
      <p class="text-xs text-muted">{{ t('researchUnverified') }}</p>
    </template>
    <UModal v-model:open="open" :title="t('researchSourceDetails')" :description="selected?.title ?? t('researchSources')" :close="false" :content="{ onCloseAutoFocus: restoreFocus }" :ui="{ content: 'research-dialog' }">
      <template #actions><UButton icon="i-lucide-x" color="neutral" variant="ghost" :aria-label="t('researchClose')" class="touch-control" @click="open = false" /></template>
      <template #body>
        <div v-if="selected" class="research-details">
          <p>{{ sourceDomain(selected.originalUrl) }} · {{ t(selected.status === 'unavailable' ? 'researchSourceUnavailable' : 'researchPrepared') }}</p>
          <p>{{ t('researchUnverified') }}</p>
          <p v-if="selected.status === 'context_prepared'">{{ t(research.modelResponseObserved ? 'researchObserved' : 'researchNotObserved') }}</p>
          <dl>
            <dt>{{ t('researchOriginalUrl') }}</dt><dd><a v-if="sourceHref(selected.originalUrl)" :href="sourceHref(selected.originalUrl)" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">{{ selected.originalUrl }}</a><span v-else>{{ selected.originalUrl }}</span></dd>
            <template v-if="selected.finalUrl && selected.finalUrl !== selected.originalUrl"><dt>{{ t('researchFinalUrl') }}</dt><dd><a v-if="sourceHref(selected.finalUrl)" :href="sourceHref(selected.finalUrl)" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">{{ selected.finalUrl }}</a><span v-else>{{ selected.finalUrl }}</span></dd></template>
            <template v-if="selected.fetchedAt"><dt>{{ t('researchFetchedAt') }}</dt><dd><time :datetime="selected.fetchedAt">{{ fetchedAt(selected.fetchedAt) }}</time></dd></template>
          </dl>
          <template v-if="selected.excerpt"><h3 class="font-medium">{{ t('researchExcerpt') }}</h3><blockquote class="research-excerpt">{{ selected.excerpt }}</blockquote></template>
          <details><summary>{{ t('researchTechnical') }}</summary><dl><dt>{{ t('researchGeneration') }}</dt><dd>{{ research.sourceGenerationId }}</dd><dt>{{ t('researchSourceId') }}</dt><dd>{{ selected.sourceId }}</dd><dt>{{ t('researchSearchRun') }}</dt><dd>{{ selected.searchRunId }}</dd><dt>{{ t('researchFetchRun') }}</dt><dd>{{ selected.fetchRunId }}</dd><template v-if="selected.contentDigest"><dt>SHA-256</dt><dd>{{ selected.contentDigest }}</dd></template></dl></details>
        </div>
      </template>
    </UModal>
  </section>
</template>
