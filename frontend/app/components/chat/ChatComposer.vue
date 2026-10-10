<script setup lang="ts">
import { CHAT_LIMITS } from '../../lib/chat/limits'
import { computed, ref } from 'vue'
import ChatModelMenu from './ChatModelMenu.vue'
import type { ChatModelId } from '../../composables/useModelSelection'

const props = defineProps<{ busy: boolean, streaming: boolean, cancellationRequested: boolean, modelUnavailable?: boolean, inputError?: string | null }>()
const text = defineModel<string>({ required: true })
const model = defineModel<ChatModelId>('model', { required: true })
const emit = defineEmits<{ send: [text: string], stop: [] }>()
const prompt = ref<{ textareaRef: HTMLTextAreaElement | undefined } | null>(null)
const tooLong = computed(() => text.value.length > CHAT_LIMITS.max_message_chars)
function submit(): void {
  if (props.busy || props.modelUnavailable || props.inputError || !text.value.trim() || tooLong.value) return
  emit('send', text.value)
}
defineExpose({ focus: () => prompt.value?.textareaRef?.focus({ preventScroll: true }) })
</script>

<template>
  <div class="composer-container">
    <UChatPrompt
      ref="prompt" v-model="text" aria-label="Nachricht" placeholder="Frag noris AI …" :autofocus="false" :rows="1"
      variant="naked" color="neutral" :maxrows="8" class="chat-composer"
      :ui="{ root: 'gap-0 p-0', header: 'composer-leading', body: 'composer-body', base: 'composer-input overflow-y-auto', footer: 'composer-toolbar' }"
      @submit="submit"
    >
      <template #header>
        <UButton disabled icon="i-lucide-plus" color="neutral" variant="ghost" class="composer-attachment touch-control" aria-label="Anhang hinzufügen – demnächst verfügbar" />
      </template>
      <template #footer>
        <ChatModelMenu v-model="model" :busy="busy" compact label="Modell im Eingabefeld auswählen" />
        <UChatPromptSubmit
          :status="busy ? (streaming ? 'streaming' : 'submitted') : 'ready'" :disabled="!busy && (!text.trim() || tooLong || modelUnavailable || !!inputError)"
          color="neutral" variant="solid" streaming-color="neutral" streaming-variant="solid" submitted-color="neutral" submitted-variant="solid"
          :aria-label="busy ? (cancellationRequested ? 'Abbruch läuft' : 'Antwort stoppen') : 'Nachricht senden'"
          :aria-disabled="cancellationRequested" class="composer-submit touch-control rounded-full" @stop="emit('stop')"
        />
      </template>
    </UChatPrompt>
    <p v-if="tooLong" role="status" class="mt-2 text-center text-xs text-error">Die Nachricht darf höchstens {{ CHAT_LIMITS.max_message_chars.toLocaleString('de-DE') }} Zeichen enthalten.</p>
  </div>
</template>
