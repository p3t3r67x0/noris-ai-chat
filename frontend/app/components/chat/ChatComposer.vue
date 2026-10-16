<script setup lang="ts">
import { useAppNotifications } from '../../composables/useAppNotifications'
import { useAppLocale } from '../../composables/useAppLocale'
import { CHAT_LIMITS } from '../../lib/chat/limits'
import { computed, nextTick, ref, useId, watch } from 'vue'
import ChatModelMenu from './ChatModelMenu.vue'
import ChatReasoningMenu from './ChatReasoningMenu.vue'
import { CHAT_MODELS } from '../../composables/useModelSelection'
import type { ReasoningPreference } from '../../lib/chat/reasoning'
import { reasoningChoices } from '../../lib/chat/reasoning'
import type { ConversationMode } from '../../lib/chat/conversations'
import type { ChatModelId } from '../../composables/useModelSelection'
import { useComposerDictation } from '../../composables/useComposerDictation'
import { useComposerAutosize } from '../../composables/useComposerAutosize'
import type { UploadEntry } from '../../composables/useChatAttachments'
import { composerMenuItems } from '../../lib/chat/composerMenu'
import { useSlashCommands } from '../../composables/useSlashCommands'
import type { CommandContext } from '../../lib/chat/commands'
import ChatCommandMenu from './ChatCommandMenu.vue'
const { t, language } = useAppLocale()
const privacyId = useId()

const props = defineProps<{ conversationId?: string | null, modelSelectionBusy?: boolean, researchAvailable?: boolean, researchError?: string | null, busy: boolean, streaming: boolean, cancellationRequested: boolean, modelUnavailable?: boolean, inputError?: string | null, files?: UploadEntry[], uploadAvailable?: boolean, uploadUnavailableReason?: string | null, uploadBlocked?: boolean, uploadError?: string | null, uploadErrorNotified?: boolean, imageSupported?: boolean, conversationMode?: ConversationMode, reasoningPreference?: ReasoningPreference | null, settingsBusy?: boolean, learningAvailable?: boolean }>()
const notifications = useAppNotifications()
const text = defineModel<string>({ required: true })
const webSearch = defineModel<boolean>('research', { default: false })
const model = defineModel<ChatModelId>('model', { required: true })
const emit = defineEmits<{ send: [text: string], stop: [], files: [files: File[]], removeFile: [key: string], retryFile: [key: string], refreshFiles: [], mode: [mode: ConversationMode], reasoning: [preference: ReasoningPreference | null] }>()
const container = ref<HTMLElement | null>(null)
const learning = computed(() => props.conversationMode === 'learning')
const selectedModel = computed(() => CHAT_MODELS.find(item => item.id === model.value))
const showReasoning = computed(() => reasoningChoices(selectedModel.value).length > 0)
const prompt = ref<{ textareaRef: HTMLTextAreaElement | undefined } | null>(null)
const hasAttachments = computed(() => Boolean(props.files?.length))
const hasHeader = computed(() => hasAttachments.value || learning.value)
const autosize = useComposerAutosize(prompt, text, hasHeader)
const dictation = useComposerDictation(text, language, focus)
watch(() => props.busy, busy => { if (busy) dictation.stop() })
watch(() => props.conversationId, dictation.stop)
function focusLeft(event: FocusEvent): void {
  if (!(event.relatedTarget instanceof Node) || !container.value?.contains(event.relatedTarget)) dictation.stop()
}
watch([learning, webSearch, showReasoning, model], () => nextTick(autosize.resize), { flush: 'post' })
const fileInput = ref<HTMLInputElement | null>(null)
const uploadMenu = ref(false)
const attachmentButton = ref<{ $el: HTMLButtonElement } | null>(null)
const modelMenu = ref<InstanceType<typeof ChatModelMenu> | null>(null)
const reasoningMenu = ref<InstanceType<typeof ChatReasoningMenu> | null>(null)
const commandContext = computed<CommandContext>(() => ({
  learning: props.learningAvailable !== false && !props.settingsBusy,
  search: props.researchAvailable === true && selectedModel.value?.researchEligible === true && !selectedModel.value.disabled && !props.researchError && !props.settingsBusy && !props.busy,
  reasoning: showReasoning.value && !props.settingsBusy && !props.busy,
  model: CHAT_MODELS.some(item => !item.disabled) && !(props.modelSelectionBusy ?? (props.busy || props.settingsBusy)),
  image: false,
  file: Boolean(props.uploadAvailable),
  actions: {
    learning: activateLearning,
    search: () => { webSearch.value = true; void nextTick(focus) },
    reasoning: () => { void nextTick(() => reasoningMenu.value?.open()) },
    model: () => { void nextTick(() => modelMenu.value?.open()) },
    file: chooseFiles,
    help: () => slash.showHelp(),
  },
}))
const slash = useSlashCommands(text, commandContext, () => prompt.value?.textareaRef, () => props.conversationId)
watch(slash.open, open => { if (open) uploadMenu.value = false })
watch(uploadMenu, open => { if (open) slash.close() })
const actionItems = computed(() => composerMenuItems(t, { upload: chooseFiles, learning: activateLearning, web: toggleSearch }, Boolean(props.uploadAvailable), props.uploadUnavailableReason, { learningAvailable: props.learningAvailable !== false && !props.settingsBusy, learningActive: learning.value, webAvailable: props.researchAvailable, webActive: webSearch.value, webReason: props.researchError }))
function focus(): void { prompt.value?.textareaRef?.focus({ preventScroll: true }) }
let returnToComposer = false
let returnToActionTrigger = false
function menuEscape(): void { returnToActionTrigger = true }
function chooseFiles(): void { returnToComposer = true; uploadMenu.value = false; fileInput.value?.click() }
function activateLearning(): void {
  returnToComposer = true
  uploadMenu.value = false
  emit('mode', 'learning')
  void nextTick(focus)
}
function toggleSearch(): void { returnToComposer = true; uploadMenu.value = false; webSearch.value = !webSearch.value; void nextTick(focus) }
function deactivateSearch(): void { webSearch.value = false; void nextTick(focus) }
function deactivateLearning(): void { emit('mode', 'normal'); void nextTick(focus) }
function inputChanged(): void {
  autosize.resize()
  slash.update()
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
    return
  }
  if (returnToComposer) { event.preventDefault(); returnToComposer = false; focus() }
  else if (returnToActionTrigger || document.activeElement === document.body || document.activeElement?.matches('.chat-main') || document.activeElement?.closest('.composer-action-menu')) {
    event.preventDefault()
    void nextTick(() => attachmentButton.value?.$el.focus({ preventScroll: true }))
  }
  returnToActionTrigger = false
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
  if (slash.guardSubmit()) return
  if (uploadMenu.value || props.settingsBusy || props.busy || props.modelUnavailable || (webSearch.value && props.researchError) || props.inputError || props.uploadBlocked || !text.value.trim() || tooLong.value) return
  dictation.stop()
  emit('send', text.value)
}
function stop(event?: Event): void {
  event?.preventDefault()
  if (!props.cancellationRequested) emit('stop')
}
defineExpose({ focus })
</script>

<template>
  <div ref="container" class="composer-container" :data-mode="conversationMode ?? 'normal'" :data-layout="autosize.maximized.value ? 'maximized' : autosize.expanded.value ? 'expanded' : 'compact'" @keydown.capture="slash.keydown" @compositionstart="slash.compositionStart" @compositionend="slash.compositionEnd" @focusout="focusLeft">
    <details v-if="uploadError && uploadErrorNotified" class="mb-2 text-xs text-muted"><summary>Anhangaktion fehlgeschlagen.</summary><p>{{ uploadError }}</p><UButton color="neutral" variant="link" label="Anhänge neu laden" @click="emit('refreshFiles')" /></details>
    <p v-else-if="uploadError" role="alert" class="mb-2 text-center text-xs text-error">{{ uploadError }}</p>
    <p v-if="tooLong" role="status" class="mb-2 text-center text-xs text-error">Die Nachricht darf höchstens {{ CHAT_LIMITS.max_message_chars.toLocaleString('de-DE') }} Zeichen enthalten.</p>
    <UChatPrompt
      ref="prompt" v-model="text" :aria-label="t('message')" :placeholder="t('prompt')" :autofocus="false" :rows="1" :aria-describedby="webSearch ? privacyId : undefined"
      variant="naked" color="neutral" :autoresize="false" class="chat-composer" :class="{ 'composer-expanded': autosize.expanded.value || autosize.stacked.value }"
      :ui="{ root: 'gap-0 p-0', header: 'composer-files', body: 'composer-body', base: 'composer-input overflow-y-auto', footer: 'composer-toolbar' }"
      :aria-controls="slash.open.value ? slash.listId : undefined"
      aria-haspopup="listbox"
      :aria-activedescendant="slash.activeId.value" aria-autocomplete="list" @submit="submit" @input="inputChanged"
      @click="slash.update" @keyup.left="slash.update" @keyup.right="slash.update"
    >
      <template v-if="hasHeader" #header>
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
              <p :role="file.status === 'failed' ? 'alert' : 'status'" :aria-live="file.status === 'failed' ? 'assertive' : 'polite'" aria-atomic="true" class="attachment-detail">
                <template v-if="file.status === 'uploading'">Wird hochgeladen …</template>
                <template v-else-if="file.status === 'removing'">Wird entfernt …</template>
                <template v-else-if="file.status === 'failed'">Fehlgeschlagen · {{ file.error }}</template>
                <template v-else-if="file.mime.startsWith('image/') && file.attachment?.modelUsable && imageSupported">Gespeichert · Für Bildanalyse bereit</template>
                <template v-else-if="file.mime.startsWith('image/')">Gespeichert · Wähle ein Modell mit Bildeingabe</template>
                <template v-else-if="file.attachment?.textReference"><span class="sr-only">Textreferenz übernommen</span></template>
                <template v-else-if="file.attachment?.modelUsable">Gespeichert · Text extrahiert</template>
                <template v-else>Gespeichert · Kein extrahierbarer Text</template>
              </p>
              <progress v-if="file.status === 'uploading'" :value="file.progress" max="100" :aria-label="`Uploadfortschritt: ${file.filename}`" class="w-full" />
            </div>
            <UButton v-if="file.status === 'failed' && (file.file || file.reference)" icon="i-lucide-rotate-cw" color="neutral" variant="ghost" class="touch-control" :aria-label="`${file.filename} erneut hochladen`" @click="retryFile(file.key)" />
            <UButton v-if="file.status === 'failed' && file.diagnostics && notifications" color="neutral" variant="ghost" label="Details" :aria-label="`${file.filename}: Fehlerdetails`" @click="notifications.details.value = file.diagnostics" />
            <UButton icon="i-lucide-x" color="neutral" variant="ghost" class="touch-control" :disabled="file.status === 'removing' || (file.status === 'uploading' && !!file.reference)" :aria-label="`${file.filename} entfernen`" @click="removeFile(file.key)" />
          </li>
        </ul>
        <div v-if="learning" class="composer-learning" :title="t('learningHint')">
          <UIcon name="i-lucide-book-open" aria-hidden="true" class="size-5 shrink-0" />
          <span role="status">{{ t('learning') }}</span>
          <UButton icon="i-lucide-x" color="neutral" variant="ghost" class="learning-remove touch-control" :disabled="settingsBusy" :aria-label="t('stopLearning')" @click="deactivateLearning" />
        </div>
      </template>
      <template v-if="webSearch" #default>
        <span class="composer-web-search" data-research-selected :title="t('researchPrivacy')">
          <UIcon name="i-lucide-globe" aria-hidden="true" class="size-6 shrink-0" />
          <span>{{ t('webSearch') }}</span>
          <UButton type="button" icon="i-lucide-x" color="neutral" variant="ghost" class="web-search-remove" :aria-label="t('webSearchOff')" @click="deactivateSearch" />
        </span>
      </template>
      <template #footer>
        <UDropdownMenu v-model:open="uploadMenu" :items="actionItems" :modal="false" :content="{ side: 'top', align: 'start', ...(container ? { reference: container } : {}), sideOffset: 10, collisionPadding: 12, loop: true, updatePositionStrategy: 'always', onEscapeKeyDown: menuEscape, onCloseAutoFocus: menuClosed }" :ui="{ content: 'composer-plus-menu composer-floating-menu composer-action-menu ring-0', viewport: 'p-0', item: 'composer-plus-menu-item composer-menu-item before:hidden', itemLeadingIcon: 'size-5 text-inherit', itemWrapper: 'composer-menu-copy', itemLabel: 'composer-menu-title', itemDescription: 'composer-menu-description' }">
          <UButton ref="attachmentButton" icon="i-lucide-plus" color="neutral" variant="ghost" class="composer-attachment touch-control" :aria-label="t('composerActions')" :title="t('composerActions')" @click="slash.close" />
        </UDropdownMenu>
        <div class="composer-model-controls">
          <ChatModelMenu ref="modelMenu" v-model="model" :busy="modelSelectionBusy ?? (busy || settingsBusy)" compact :label="t('composerModel')" />
          <ChatReasoningMenu v-if="showReasoning" ref="reasoningMenu" :model="selectedModel" :preference="reasoningPreference" :disabled="settingsBusy || busy" :anchor="container" @select="emit('reasoning', $event)" />
        </div>
        <UButton type="button" :icon="dictation.listening.value ? 'i-lucide-mic-off' : 'i-lucide-mic'" color="neutral" variant="ghost" class="composer-microphone touch-control" :class="{ 'is-listening': dictation.listening.value }" :disabled="!dictation.supported.value || busy" :aria-pressed="dictation.listening.value" :aria-label="t(dictation.listening.value ? 'stopDictation' : 'startDictation')" :title="t(dictation.supported.value ? 'startDictation' : 'dictationUnavailable')" @click="dictation.toggle" />
        <UChatPromptSubmit
          :status="busy ? (streaming ? 'streaming' : 'submitted') : 'ready'" :disabled="!busy && (settingsBusy || !text.trim() || tooLong || modelUnavailable || (webSearch && !!researchError) || !!inputError || uploadBlocked)"
          color="neutral" variant="solid" streaming-color="neutral" streaming-variant="solid" submitted-color="neutral" submitted-variant="solid"
          :aria-label="busy ? (cancellationRequested ? t('stopping') : t('stopResponse')) : t('sendMessage')"
          :aria-disabled="cancellationRequested" class="composer-submit touch-control rounded-full" @stop="stop"
        />
      </template>
    </UChatPrompt>
    <ChatCommandMenu v-model:open="slash.open.value" :anchor="container" :input="prompt?.textareaRef" :items="slash.items.value" :active="slash.active.value" :list-id="slash.listId" :help="slash.help.value" @select="slash.execute($event)" @active="slash.active.value = $event" @close="slash.close" />
    <p v-if="slash.unavailable.value" role="status" class="mt-2 text-sm text-muted">{{ t('commandUnavailable') }}</p>
    <p v-if="webSearch" :id="privacyId" class="research-privacy sr-only">{{ t('researchPrivacy') }}</p>
    <p v-if="dictation.error.value" role="status" class="mt-2 text-sm text-error">{{ t('dictationFailed') }}</p>
    <p v-if="webSearch && researchError" role="status" aria-live="polite" class="mt-2 text-sm text-error">{{ researchError }}</p>
    <input ref="fileInput" type="file" hidden multiple accept=".txt,.md,.markdown,.pdf,.png,.jpg,.jpeg" aria-label="Dateien hinzufügen" @change="filesSelected" @cancel="focus">
  </div>
</template>
