<script setup lang="ts">
import { useAppLocale } from '../../composables/useAppLocale'
import { CHAT_LIMITS } from '../../lib/chat/limits'
import { computed, ref } from 'vue'
import ChatModelMenu from './ChatModelMenu.vue'
import type { ChatModelId } from '../../composables/useModelSelection'
import { useComposerAutosize } from '../../composables/useComposerAutosize'
const { t } = useAppLocale()

const props = defineProps<{ busy: boolean, streaming: boolean, cancellationRequested: boolean, modelUnavailable?: boolean, inputError?: string | null }>()
const text = defineModel<string>({ required: true })
const model = defineModel<ChatModelId>('model', { required: true })
const emit = defineEmits<{ send: [text: string], stop: [] }>()
const prompt = ref<{ textareaRef: HTMLTextAreaElement | undefined } | null>(null)
const autosize = useComposerAutosize(prompt, text)
function focus(): void { prompt.value?.textareaRef?.focus({ preventScroll: true }) }
const tooLong = computed(() => text.value.length > CHAT_LIMITS.max_message_chars)
function submit(): void {
  if (props.busy || props.modelUnavailable || props.inputError || !text.value.trim() || tooLong.value) return
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
    <p v-if="tooLong" role="status" class="mb-2 text-center text-xs text-error">Die Nachricht darf höchstens {{ CHAT_LIMITS.max_message_chars.toLocaleString('de-DE') }} Zeichen enthalten.</p>
    <UChatPrompt
      ref="prompt" v-model="text" :aria-label="t('message')" :placeholder="t('prompt')" :autofocus="false" :rows="1"
      variant="naked" color="neutral" :autoresize="false" class="chat-composer" :class="{ 'composer-expanded': autosize.expanded.value }"
      :ui="{ root: 'gap-0 p-0', body: 'composer-body', base: 'composer-input overflow-y-auto', footer: 'composer-toolbar' }"
      @submit="submit"
      @input="autosize.resize"
    >
      <template #footer>
        <UButton disabled icon="i-lucide-plus" color="neutral" variant="ghost" class="composer-attachment touch-control" :aria-label="t('attachment')" />
        <ChatModelMenu v-model="model" :busy="busy" compact :label="t('composerModel')" />
        <UChatPromptSubmit
          :status="busy ? (streaming ? 'streaming' : 'submitted') : 'ready'" :disabled="!busy && (!text.trim() || tooLong || modelUnavailable || !!inputError)"
          color="neutral" variant="solid" streaming-color="neutral" streaming-variant="solid" submitted-color="neutral" submitted-variant="solid"
          :aria-label="busy ? (cancellationRequested ? t('stopping') : t('stopResponse')) : t('sendMessage')"
          :aria-disabled="cancellationRequested" class="composer-submit touch-control rounded-full" @stop="stop"
        />
      </template>
    </UChatPrompt>
  </div>
</template>
