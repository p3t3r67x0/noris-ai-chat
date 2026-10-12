<script setup lang="ts">
import { useAppLocale } from '../../composables/useAppLocale'
import { CHAT_LIMITS } from '../../lib/chat/limits'
import { computed, nextTick, ref, watch } from 'vue'
import ChatModelMenu from './ChatModelMenu.vue'
import ChatReasoningMenu from './ChatReasoningMenu.vue'
import { CHAT_MODELS } from '../../composables/useModelSelection'
import type { ReasoningPreference } from '../../lib/chat/reasoning'
import { reasoningChoices } from '../../lib/chat/reasoning'
import type { ConversationMode } from '../../lib/chat/conversations'
import type { ChatModelId } from '../../composables/useModelSelection'
import { useComposerAutosize } from '../../composables/useComposerAutosize'
import type { UploadEntry } from '../../composables/useChatAttachments'
import { composerMenuItems } from '../../lib/chat/composerMenu'
const { t } = useAppLocale()

const props = defineProps<{ busy: boolean, streaming: boolean, cancellationRequested: boolean, modelUnavailable?: boolean, inputError?: string | null, files?: UploadEntry[], uploadAvailable?: boolean, uploadUnavailableReason?: string | null, uploadBlocked?: boolean, uploadError?: string | null, imageSupported?: boolean, conversationMode?: ConversationMode, reasoningPreference?: ReasoningPreference | null, settingsBusy?: boolean, learningAvailable?: boolean }>()
const text = defineModel<string>({ required: true })
const model = defineModel<ChatModelId>('model', { required: true })
const emit = defineEmits<{ send: [text: string], stop: [], files: [files: File[]], removeFile: [key: string], retryFile: [key: string], mode: [mode: ConversationMode], reasoning: [preference: ReasoningPreference | null] }>()
const container = ref<HTMLElement | null>(null)
const learning = computed(() => props.conversationMode === 'learning')
const selectedModel = computed(() => CHAT_MODELS.find(item => item.id === model.value))
const showReasoning = computed(() => reasoningChoices(selectedModel.value).length > 0)
const prompt = ref<{ textareaRef: HTMLTextAreaElement | undefined } | null>(null)
const hasAttachments = computed(() => Boolean(props.files?.length))
const autosize = useComposerAutosize(prompt, text, hasAttachments)
watch([learning, showReasoning, model], () => nextTick(autosize.resize), { flush: 'post' })
const fileInput = ref<HTMLInputElement | null>(null)
const uploadMenu = ref(false)
const attachmentButton = ref<{ $el: HTMLButtonElement } | null>(null)
const slashRange = ref<{ start: number, end: number } | null>(null)
const actionItems = computed(() => composerMenuItems(t, { upload: chooseFiles, learning: activateLearning }, Boolean(props.uploadAvailable), props.uploadUnavailableReason, { learningAvailable: props.learningAvailable !== false && !props.settingsBusy, learningActive: learning.value }))
function focus(): void { prompt.value?.textareaRef?.focus({ preventScroll: true }) }
let returnToComposer = false
let returnToActionTrigger = false
function menuEscape(): void { returnToActionTrigger = true }
function removeSlash(): void {
  const range = slashRange.value
  if (range && /^\/(?:lernen|learn)?$/i.test(text.value.slice(range.start, range.end))) {
    text.value = text.value.slice(0, range.start) + text.value.slice(range.end)
  }
  slashRange.value = null
}
function chooseFiles(): void { removeSlash(); returnToComposer = true; fileInput.value?.click() }
function activateLearning(): void {
  removeSlash()
  returnToComposer = true
  uploadMenu.value = false
  emit('mode', 'learning')
  void nextTick(focus)
}
function deactivateLearning(): void { emit('mode', 'normal'); void nextTick(focus) }
function inputChanged(): void {
  autosize.resize()
  const input = prompt.value?.textareaRef
  if (!input) return
  const caret = input.selectionStart
  const before = input.value.slice(0, caret)
  const match = /(?:^|\s)(\/(?:lernen|learn)?)$/i.exec(before)
  if (match) {
    slashRange.value = { start: caret - match[1]!.length, end: caret }
    uploadMenu.value = true
  }
  else if (slashRange.value) { returnToComposer = true; slashRange.value = null; uploadMenu.value = false }
}
function menuKeydown(event: KeyboardEvent): void {
  if (!uploadMenu.value || event.isComposing) return
  if (['ArrowDown', 'ArrowUp', 'Enter'].includes(event.key)) {
    event.preventDefault()
    event.stopPropagation()
    const items = [...document.querySelectorAll<HTMLElement>('.composer-action-menu [role="menuitem"]:not([data-disabled])')]
    ;(event.key === 'ArrowUp' ? items.at(-1) : items[0])?.focus()
    if (event.key === 'Enter') items[0]?.click()
  }
  else if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); returnToComposer = true; uploadMenu.value = false; slashRange.value = null; focus() }
}
function menuClosed(event: Event): void {
  // Closing animations can finish after the user has opened another control.
  // Preserve that newer focus instead of dismissing its menu via the textarea.
  const active = document.activeElement
  if (active && active !== document.body && active !== prompt.value?.textareaRef
    && active !== fileInput.value && active !== attachmentButton.value?.$el
    && !active.matches('.chat-main') && !active.closest('.composer-action-menu')) {
    event.preventDefault()
    returnToComposer = false
    returnToActionTrigger = false
    slashRange.value = null
    return
  }
  if (returnToComposer || slashRange.value) { event.preventDefault(); returnToComposer = false; slashRange.value = null; focus() }
  else if (returnToActionTrigger || document.activeElement === document.body || document.activeElement?.matches('.chat-main') || document.activeElement?.closest('.composer-action-menu')) {
    event.preventDefault()
    void nextTick(() => attachmentButton.value?.$el.focus({ preventScroll: true }))
  }
  returnToActionTrigger = false
}
function menuFocusOutside(event: Event): void {
  const original = (event as CustomEvent<{ originalEvent: FocusEvent }>).detail?.originalEvent
  if (slashRange.value && original?.target === prompt.value?.textareaRef) event.preventDefault()
}
function removeFile(key: string): void { emit('removeFile', key); focus() }
function retryFile(key: string): void { emit('retryFile', key); focus() }
async function filesSelected(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const selected = [...input.files ?? []]
  if (selected.length) emit('files', selected)
  input.value = ''
  await nextTick()
  focus()
}
function sizeLabel(bytes: number): string { return bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB` }
const tooLong = computed(() => text.value.length > CHAT_LIMITS.max_message_chars)
function submit(): void {
  if (uploadMenu.value || props.settingsBusy || props.busy || props.modelUnavailable || props.inputError || props.uploadBlocked || !text.value.trim() || tooLong.value) return
  emit('send', text.value)
}
function stop(event?: Event): void {
  event?.preventDefault()
  if (!props.cancellationRequested) emit('stop')
}
defineExpose({ focus })
</script>

<template>
  <div ref="container" class="composer-container" :data-mode="conversationMode ?? 'normal'" :data-layout="autosize.maximized.value ? 'maximized' : autosize.expanded.value ? 'expanded' : 'compact'" @keydown.capture="menuKeydown">
    <p v-if="uploadError" role="alert" class="mb-2 text-center text-xs text-error">{{ uploadError }}</p>
    <p v-if="tooLong" role="status" class="mb-2 text-center text-xs text-error">Die Nachricht darf höchstens {{ CHAT_LIMITS.max_message_chars.toLocaleString('de-DE') }} Zeichen enthalten.</p>
    <UChatPrompt
      ref="prompt" v-model="text" :aria-label="t('message')" :placeholder="t('prompt')" :autofocus="false" :rows="1"
      variant="naked" color="neutral" :autoresize="false" class="chat-composer" :class="{ 'composer-expanded': autosize.expanded.value }"
      :ui="{ root: 'gap-0 p-0', header: 'composer-files', body: 'composer-body', base: 'composer-input overflow-y-auto', footer: 'composer-toolbar' }"
      @submit="submit"
      @input="inputChanged"
    >
      <template v-if="hasAttachments || learning" #header>
        <ul v-if="hasAttachments" class="attachment-list" aria-label="Anhänge und Textreferenzen">
          <li v-for="file in files" :key="file.key" class="attachment-preview" :data-upload-status="file.status">
            <UIcon :name="file.mime.startsWith('image/') ? 'i-lucide-image' : 'i-lucide-file-text'" class="size-6 shrink-0" aria-hidden="true" />
            <div class="attachment-copy">
              <p class="attachment-filename" :title="file.filename">{{ file.filename }}</p>
              <details v-if="file.reference || file.attachment?.textReference" class="text-reference-details">
                <summary class="text-reference-excerpt" :title="(file.reference || file.attachment?.textReference)?.text" aria-label="Vollständigen markierten Text anzeigen">„{{ (file.reference || file.attachment?.textReference)?.text }}“</summary>
                <p class="text-reference-full">{{ (file.reference || file.attachment?.textReference)?.text }}</p>
              </details>
              <p v-else class="attachment-detail">{{ file.mime || 'Datei' }} · {{ sizeLabel(file.size) }}</p>
              <p role="status" aria-live="polite" aria-atomic="true" class="attachment-detail">
                <template v-if="file.status === 'uploading'">Wird hochgeladen …</template>
                <template v-else-if="file.status === 'removing'">Wird entfernt …</template>
                <template v-else-if="file.status === 'failed'">{{ file.error }}</template>
                <template v-else-if="file.mime.startsWith('image/') && file.attachment?.modelUsable && imageSupported">Gespeichert · Für Bildanalyse bereit</template>
                <template v-else-if="file.mime.startsWith('image/')">Gespeichert · Wähle ein Modell mit Bildeingabe</template>
                <template v-else-if="file.attachment?.textReference"><span class="sr-only">Textreferenz übernommen</span></template>
                <template v-else-if="file.attachment?.modelUsable">Gespeichert · Text extrahiert</template>
                <template v-else>Gespeichert · Kein extrahierbarer Text</template>
              </p>
              <progress v-if="file.status === 'uploading'" :value="file.progress" max="100" :aria-label="`Uploadfortschritt: ${file.filename}`" class="w-full" />
            </div>
            <UButton v-if="file.status === 'failed' && (file.file || file.reference)" icon="i-lucide-rotate-cw" color="neutral" variant="ghost" class="touch-control" :aria-label="`${file.filename} erneut hochladen`" @click="retryFile(file.key)" />
            <UButton icon="i-lucide-x" color="neutral" variant="ghost" class="touch-control" :disabled="file.status === 'removing' || (file.status === 'uploading' && !!file.reference)" :aria-label="`${file.filename} entfernen`" @click="removeFile(file.key)" />
          </li>
        </ul>
        <div v-if="learning" class="composer-learning">
          <UIcon name="i-lucide-book-open" aria-hidden="true" class="size-5 shrink-0" />
          <span role="status">{{ t('learning') }}</span>
          <UButton icon="i-lucide-x" color="neutral" variant="ghost" class="learning-remove touch-control" :disabled="settingsBusy" :aria-label="t('stopLearning')" @click="deactivateLearning" />
        </div>
      </template>
      <template #footer>
        <UDropdownMenu v-model:open="uploadMenu" :items="actionItems" :modal="false" :content="{ side: 'top', align: 'start', ...(container ? { reference: container } : {}), sideOffset: 10, collisionPadding: 12, loop: true, updatePositionStrategy: 'always', onEscapeKeyDown: menuEscape, onCloseAutoFocus: menuClosed, onFocusOutside: menuFocusOutside }" :ui="{ content: 'composer-plus-menu composer-floating-menu composer-action-menu ring-0', viewport: 'p-0', item: 'composer-plus-menu-item composer-menu-item before:hidden', itemLeadingIcon: 'size-5 text-inherit', itemWrapper: 'composer-menu-copy', itemLabel: 'composer-menu-title', itemDescription: 'composer-menu-description' }">
          <UButton ref="attachmentButton" icon="i-lucide-plus" color="neutral" variant="ghost" class="composer-attachment touch-control" :aria-label="t('composerActions')" :title="t('composerActions')" @click="slashRange = null" />
        </UDropdownMenu>
        <div class="composer-model-controls">
          <ChatModelMenu v-model="model" :busy="busy || settingsBusy" compact :label="t('composerModel')" />
          <ChatReasoningMenu v-if="showReasoning" :model="selectedModel" :preference="reasoningPreference" :disabled="settingsBusy || busy" :anchor="container" @select="emit('reasoning', $event)" />
        </div>
        <UChatPromptSubmit
          :status="busy ? (streaming ? 'streaming' : 'submitted') : 'ready'" :disabled="!busy && (settingsBusy || !text.trim() || tooLong || modelUnavailable || !!inputError || uploadBlocked)"
          color="neutral" variant="solid" streaming-color="neutral" streaming-variant="solid" submitted-color="neutral" submitted-variant="solid"
          :aria-label="busy ? (cancellationRequested ? t('stopping') : t('stopResponse')) : t('sendMessage')"
          :aria-disabled="cancellationRequested" class="composer-submit touch-control rounded-full" @stop="stop"
        />
      </template>
    </UChatPrompt>
    <input ref="fileInput" type="file" hidden multiple accept=".txt,.md,.markdown,.pdf,.png,.jpg,.jpeg" aria-label="Dateien hinzufügen" @change="filesSelected" @cancel="focus">
  </div>
</template>
