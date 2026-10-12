<script setup lang="ts">
import { useAppLocale } from '../../composables/useAppLocale'
import { CHAT_LIMITS } from '../../lib/chat/limits'
import { computed, nextTick, ref } from 'vue'
import ChatModelMenu from './ChatModelMenu.vue'
import type { ChatModelId } from '../../composables/useModelSelection'
import { useComposerAutosize } from '../../composables/useComposerAutosize'
import type { UploadEntry } from '../../composables/useChatAttachments'
import { composerMenuItems } from '../../lib/chat/composerMenu'
const { t } = useAppLocale()

const props = defineProps<{ busy: boolean, streaming: boolean, cancellationRequested: boolean, modelUnavailable?: boolean, inputError?: string | null, files?: UploadEntry[], uploadAvailable?: boolean, uploadUnavailableReason?: string | null, uploadBlocked?: boolean, uploadError?: string | null, imageSupported?: boolean }>()
const text = defineModel<string>({ required: true })
const model = defineModel<ChatModelId>('model', { required: true })
const emit = defineEmits<{ send: [text: string], stop: [], files: [files: File[]], removeFile: [key: string], retryFile: [key: string] }>()
const prompt = ref<{ textareaRef: HTMLTextAreaElement | undefined } | null>(null)
const hasAttachments = computed(() => Boolean(props.files?.length))
const autosize = useComposerAutosize(prompt, text, hasAttachments)
const fileInput = ref<HTMLInputElement | null>(null)
const uploadMenu = ref(false)
const menuItems = computed(() => composerMenuItems(t, { upload: chooseFiles }, Boolean(props.uploadAvailable), props.uploadUnavailableReason))
const attachmentButton = ref<{ $el: HTMLButtonElement } | null>(null)
const menuReference = computed(() => {
  const button = attachmentButton.value?.$el
  const composer = button?.closest('.chat-composer')
  if (!button || !composer) return undefined
  return {
    contextElement: button,
    getBoundingClientRect: () => {
      const anchor = button.getBoundingClientRect()
      const container = composer.getBoundingClientRect()
      // Reuse Reka positioning: align with +, clear the full composer height,
      // and remeasure when wrapping or the keyboard changes its position.
      return new DOMRect(anchor.x, container.y, anchor.width, container.height)
    },
  }
})
function focus(): void { prompt.value?.textareaRef?.focus({ preventScroll: true }) }
let returnToComposer = false
function chooseFiles(): void { returnToComposer = true; fileInput.value?.click() }
function menuClosed(event: Event): void {
  if (returnToComposer) { event.preventDefault(); returnToComposer = false; focus() }
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
  if (props.busy || props.modelUnavailable || props.inputError || props.uploadBlocked || !text.value.trim() || tooLong.value) return
  emit('send', text.value)
}
function stop(event?: Event): void {
  event?.preventDefault()
  if (!props.cancellationRequested) emit('stop')
}
defineExpose({ focus })
</script>

<template>
  <div class="composer-container" :data-layout="autosize.maximized.value ? 'maximized' : autosize.expanded.value ? 'expanded' : 'compact'">
    <p v-if="uploadError" role="alert" class="mb-2 text-center text-xs text-error">{{ uploadError }}</p>
    <p v-if="tooLong" role="status" class="mb-2 text-center text-xs text-error">Die Nachricht darf höchstens {{ CHAT_LIMITS.max_message_chars.toLocaleString('de-DE') }} Zeichen enthalten.</p>
    <UChatPrompt
      ref="prompt" v-model="text" :aria-label="t('message')" :placeholder="t('prompt')" :autofocus="false" :rows="1"
      variant="naked" color="neutral" :autoresize="false" class="chat-composer" :class="{ 'composer-expanded': autosize.expanded.value }"
      :ui="{ root: 'gap-0 p-0', header: 'composer-files', body: 'composer-body', base: 'composer-input overflow-y-auto', footer: 'composer-toolbar' }"
      @submit="submit"
      @input="autosize.resize"
    >
      <template v-if="hasAttachments" #header>
        <ul class="attachment-list" aria-label="Anhänge und Textreferenzen">
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
      </template>
      <template #footer>
        <UDropdownMenu
          v-model:open="uploadMenu" :items="menuItems"
          :content="{ side: 'top', align: 'start', sideOffset: 8, ...(menuReference ? { reference: menuReference } : {}), collisionPadding: 12, avoidCollisions: true, loop: true, updatePositionStrategy: 'always', onCloseAutoFocus: menuClosed }"
          :ui="{ content: 'composer-plus-menu ring-0', viewport: 'p-0', group: 'p-2', item: 'composer-plus-menu-item before:hidden', itemLeadingIcon: 'size-5 text-inherit', itemWrapper: 'composer-plus-menu-copy', itemLabel: 'composer-plus-menu-label', itemDescription: 'composer-plus-menu-description' }"
        >
          <UButton ref="attachmentButton" icon="i-lucide-plus" color="neutral" variant="ghost" class="composer-attachment touch-control" :aria-label="t('composerActions')" :title="t('composerActions')" />
        </UDropdownMenu>
        <ChatModelMenu v-model="model" :busy="busy" compact :label="t('composerModel')" />
        <UChatPromptSubmit
          :status="busy ? (streaming ? 'streaming' : 'submitted') : 'ready'" :disabled="!busy && (!text.trim() || tooLong || modelUnavailable || !!inputError || uploadBlocked)"
          color="neutral" variant="solid" streaming-color="neutral" streaming-variant="solid" submitted-color="neutral" submitted-variant="solid"
          :aria-label="busy ? (cancellationRequested ? t('stopping') : t('stopResponse')) : t('sendMessage')"
          :aria-disabled="cancellationRequested" class="composer-submit touch-control rounded-full" @stop="stop"
        />
      </template>
    </UChatPrompt>
    <input ref="fileInput" type="file" hidden multiple accept=".txt,.md,.markdown,.pdf,.png,.jpg,.jpeg" aria-label="Dateien hinzufügen" @change="filesSelected" @cancel="focus">
  </div>
</template>
