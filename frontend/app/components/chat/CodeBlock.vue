<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import type { ThemedToken } from 'shiki'
import { useCopy } from '../../composables/useCopy'

const props = defineProps<{ code: string, language: string }>()
const { copy, copied, copyError } = useCopy()
const tokens = ref<ThemedToken[][] | null>(null)
let revision = 0
onMounted(() => {
  watch(() => [props.code, props.language], async () => {
    const current = ++revision
    tokens.value = null
    if (props.code.length > 16_000) return
    try {
      const { getHighlighter } = await import('../../lib/chat/highlight')
      const highlighter = await getHighlighter()
      const language = ({ py: 'python', js: 'javascript', ts: 'typescript', sh: 'bash' } as Record<string, string>)[props.language] ?? props.language
      if (!highlighter.getLoadedLanguages().includes(language)) return
      const result = highlighter.codeToTokens(props.code, { lang: language, themes: { light: 'github-light', dark: 'github-dark' } }).tokens
      if (current === revision) tokens.value = result
    }
    catch { /* Plain text remains readable if highlighting cannot be loaded. */ }
  }, { immediate: true })
})
</script>

<template>
  <figure class="code-block">
    <figcaption class="flex items-center justify-between gap-2 px-4 py-1 text-xs text-muted">
      <span>{{ language || 'Text' }}</span>
      <UButton :icon="copied ? 'i-lucide-check' : 'i-lucide-copy'" color="neutral" variant="ghost" size="xs" class="touch-control" :label="copied ? 'Kopiert' : 'Code kopieren'" @click="copy(code)" />
    </figcaption>
    <pre tabindex="0" :aria-label="`Codeblock ${language || 'Text'}`"><code v-if="tokens"><template v-for="(line, index) in tokens" :key="index"><span v-for="(token, tokenIndex) in line" :key="tokenIndex" :style="token.htmlStyle" :class="{ 'syntax-token': Boolean(token.htmlStyle) }">{{ token.content }}</span><template v-if="index < tokens.length - 1">{{ '\n' }}</template></template></code><code v-else>{{ code }}</code></pre>
    <p v-if="copyError" role="status" class="px-4 pb-2 text-xs text-error">{{ copyError }}</p>
  </figure>
</template>
