<script setup lang="ts">
import type { ChatMessage } from '../../lib/chat/types'
import { useCopy } from '../../composables/useCopy'
import MarkdownContent from './MarkdownContent'
import ResearchPanel from './ResearchPanel.vue'
import { useAppLocale } from '../../composables/useAppLocale'
import { researchErrorKey } from '../../lib/chat/research'
import type { ApiSchemas } from '../../types/generated/api'
import MessageVariants from './MessageVariants.vue'
import { CHAT_LIMITS } from '../../lib/chat/limits'
import { computed, ref } from 'vue'
import { formatDiagnostics, normalizeAppError } from '../../lib/notifications/errors'

const props = withDefaults(defineProps<{ message: ChatMessage, summary?: ApiSchemas['VariantSummary'] | undefined, variants?: readonly ChatMessage[], busy?: boolean, canContinue?: boolean }>(), { summary: undefined, variants: () => [], busy: false, canContinue: false })
const failure = computed(() => {
  const timestamp = new Date(props.message.errorDiagnostics?.timestamp ?? props.message.createdAt)
  return normalizeAppError({ code: props.message.errorCode, requestId: props.message.errorDiagnostics?.requestId }, { operation: 'generation', conversationId: props.message.conversationId, generationId: props.message.generationId ?? null }, Number.isFinite(timestamp.getTime()) ? timestamp : new Date())
})
const emit = defineEmits<{ edit: [], regenerate: [], continue: [], rendered: [], selectVariant: [id: string] }>()
const { copy, copied, copyError } = useCopy()
const { t } = useAppLocale()
const researchPanel = ref<InstanceType<typeof ResearchPanel> | null>(null)
const failedImages = ref<Record<string, boolean>>({})
function imageFailed(id: string): void { failedImages.value[id] = true; emit('rendered') }
function retryImage(id: string): void { failedImages.value[id] = false }
</script>

<template>
  <article :class="['chat-message', `message-${message.role}`]" :data-message-id="message.id" :data-status="message.status" :aria-label="message.role === 'user' ? 'Deine Nachricht' : 'Antwort von noris AI'">
    <p v-if="message.role === 'user'" class="user-bubble" data-selectable-message>{{ message.content }}</p>
    <ul v-if="message.role === 'user' && message.attachments?.length" class="message-attachments" aria-label="Gesendete Dateien">
      <li v-for="file in message.attachments" :key="file.id">
        <details v-if="file.textReference" class="message-attachment text-reference-details">
          <summary class="text-reference-excerpt" :title="file.textReference.text">📄 Markierter Text: „{{ file.textReference.text }}“</summary>
          <p class="text-reference-full">{{ file.textReference.text }}</p>
        </details>
        <template v-else-if="file.mimeType === 'image/png' || file.mimeType === 'image/jpeg'">
          <img v-if="!failedImages[file.id]" :src="`/api/v1/chat/attachments/${encodeURIComponent(file.id)}/content?preview=true`" :alt="`Angehängtes Bild: ${file.originalFilename}`" class="message-attachment-image" width="256" height="256" loading="lazy" decoding="async" @load="emit('rendered')" @error="imageFailed(file.id)">
          <div v-else role="status" class="message-image-error">
            <span>Bildvorschau konnte nicht geladen werden.</span>
            <UButton color="neutral" variant="link" :aria-label="`${file.originalFilename}: Bildvorschau erneut laden`" label="Erneut laden" @click="retryImage(file.id)" />
          </div>
        </template>
        <a v-if="!file.textReference" :href="`/api/v1/chat/attachments/${encodeURIComponent(file.id)}/content`" class="message-attachment" :title="file.originalFilename" download>
          <UIcon :name="file.mimeType.startsWith('image/') ? 'i-lucide-image' : 'i-lucide-file-text'" aria-hidden="true" class="size-5 shrink-0" />
          <span class="min-w-0 truncate">{{ file.originalFilename }}</span>
          <span class="shrink-0 text-xs text-muted">{{ Math.ceil(file.sizeBytes / 1024) }} KB</span>
        </a>
      </li>
    </ul>
    <div v-if="message.role === 'assistant'" class="assistant-content">
      <ResearchPanel v-if="message.research" ref="researchPanel" :research="message.research" :error-code="message.errorCode" :load-failed="message.researchLoadFailed" />
      <div v-if="message.content" data-selectable-message><MarkdownContent :content="message.content" :streaming="message.status === 'streaming'" :citations="message.research?.citations ?? []" @citation="(marker, event) => researchPanel?.openCitation(marker, event)" @rendered="emit('rendered')" /></div>
      <div v-else-if="message.status === 'submitting' || message.status === 'streaming'" class="thinking-dot" aria-hidden="true" />
      <p v-if="message.status === 'cancelled'" class="mt-3 text-xs text-muted">Antwort gestoppt.</p>
      <p v-else-if="message.status === 'incomplete'" class="mt-3 text-xs text-muted">Antwort unvollständig.</p>
      <div v-else-if="message.status === 'failed'" class="mt-3 text-xs text-muted">
        <span>Antwort fehlgeschlagen.</span>
        <UButton color="neutral" variant="link" label="Erneut versuchen" :disabled="busy" @click="emit('regenerate')" />
      </div>
      <details v-if="message.status === 'failed' || (message.status === 'incomplete' && message.errorCode)" class="message-error-details text-xs text-muted"><summary>Fehlerdetails</summary><p>{{ message.research ? t(researchErrorKey(message.errorCode)) : failure.message }}</p><pre class="notification-diagnostics">{{ formatDiagnostics(failure.diagnostics) }}</pre></details>
      <UButton v-if="canContinue" color="neutral" variant="outline" label="Weiterschreiben" class="mt-3 min-h-11" :disabled="busy" @click="emit('continue')" />
      <p v-if="message.status === 'incomplete' && !message.errorMessage && (message.continuationCount ?? 0) >= CHAT_LIMITS.max_continuations" class="mt-3 text-xs text-muted">Fortsetzungslimit erreicht. Der bisherige Text bleibt erhalten.</p>
      <p v-else-if="message.status === 'incomplete' && message.content.length >= CHAT_LIMITS.max_response_chars" class="mt-3 text-xs text-muted">Die Größenbegrenzung dieser Antwort ist erreicht.</p>
    </div>
    <div v-if="(message.content || (message.role === 'assistant' && message.status === 'failed')) && message.status !== 'streaming' && message.status !== 'submitting'" class="message-actions">
      <UButton v-if="message.content" :icon="copied ? 'i-lucide-check' : 'i-lucide-copy'" color="neutral" variant="ghost" class="touch-control" :aria-label="copied ? 'Nachricht kopiert' : 'Nachricht kopieren'" @click="copy(message.content)" />
      <UButton v-if="message.role === 'user'" icon="i-lucide-pencil" color="neutral" variant="ghost" class="touch-control" aria-label="Nachricht bearbeiten" :disabled="busy" @click="emit('edit')" />
      <UButton v-else-if="message.status !== 'failed'" icon="i-lucide-rotate-ccw" color="neutral" variant="ghost" class="touch-control" aria-label="Antwort erneut generieren" :disabled="busy" @click="emit('regenerate')" />
      <MessageVariants :variants="variants" :summary="summary" :selected-id="message.id" :busy="busy" :role="message.role" @select="emit('selectVariant', $event)" />
    </div>
    <p v-if="copyError" role="status" class="text-xs text-error">{{ copyError }}</p>
  </article>
</template>
