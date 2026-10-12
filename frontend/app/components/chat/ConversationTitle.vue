<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import type { Conversation } from '../../lib/chat/conversations'
import { automaticTitleCandidates, FALLBACK_TITLE } from '../../lib/chat/titles'

const props = defineProps<{ title: string, source: Conversation['titleSource'] }>()
const displayTitle = ref(props.title)
const element = ref<HTMLElement | null>(null)
let observer: ResizeObserver | undefined
let mounted = false

function fit(): void {
  displayTitle.value = props.title
  const label = element.value
  if (!mounted || !label || props.source === 'manual' || label.clientWidth === 0 || !label.getClientRects().length) return
  const measurement = document.createElement('span')
  measurement.style.cssText = 'position:fixed;visibility:hidden;display:inline-block;width:max-content;white-space:pre;pointer-events:none'
  measurement.setAttribute('aria-hidden', 'true')
  label.append(measurement)
  try {
    // DOM layout includes the actual font, size, weight and letter spacing.
    const title = automaticTitleCandidates(props.title).find((candidate) => {
      // Width is presentation only. Never replace a real topic with a placeholder.
      if (candidate === FALLBACK_TITLE && props.title !== candidate) return false
      measurement.textContent = candidate
      return measurement.getBoundingClientRect().width <= label.clientWidth - 1
    })
    if (title) displayTitle.value = title
  }
  finally { measurement.remove() }
}

watch(() => [props.title, props.source], fit, { flush: 'post' })
onMounted(() => {
  mounted = true
  observer = new ResizeObserver(fit)
  if (element.value) observer.observe(element.value)
  window.addEventListener('resize', fit)
  document.fonts?.addEventListener('loadingdone', fit)
  void document.fonts?.ready.then(fit)
  fit()
})
onUnmounted(() => {
  mounted = false
  observer?.disconnect()
  window.removeEventListener('resize', fit)
  document.fonts?.removeEventListener('loadingdone', fit)
})
</script>

<template>
  <span ref="element" :data-title-source="source">{{ displayTitle }}</span>
</template>
