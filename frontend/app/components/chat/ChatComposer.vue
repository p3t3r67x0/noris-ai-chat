<script setup lang="ts">
import { computed, ref } from 'vue'
import ChatModelMenu from './ChatModelMenu.vue'
import type { ChatModelId } from '../../composables/useModelSelection'
import { MAX_MESSAGE_LENGTH } from '../../lib/chat/types'

const props = defineProps<{ busy: boolean, streaming: boolean, cancellationRequested: boolean, modelUnavailable?: boolean }>()
const text = defineModel<string>({ required: true })
const model = defineModel<ChatModelId>('model', { required: true })
const emit = defineEmits<{ send: [text: string], stop: [] }>()
const prompt = ref<{ textareaRef: HTMLTextAreaElement | undefined } | null>(null)
const tooLong = computed(() => text.value.length > MAX_MESSAGE_LENGTH)
function submit(): void {
  if (props.busy || props.modelUnavailable || !text.value.trim() || tooLong.value) return
  emit('send', text.value)
}
defineExpose({ focus: () => prompt.value?.textareaRef?.focus({ preventScroll: true }) })
</script>

<template>
  <div class="composer-container">
    <UChatPrompt
      ref="prompt" v-model="text" aria-label="Nachricht" placeholder="Frag noris AI …" :autofocus="false" :rows="1"
      variant="naked" color="neutral" :maxrows="8" :maxlength="MAX_MESSAGE_LENGTH * 2" class="chat-composer"
      :ui="{ root: 'gap-0 p-0', base: 'composer-input overflow-y-auto', footer: 'composer-toolbar' }"
      @submit="submit"
    >
      <template #footer>
        <UButton disabled icon="i-lucide-plus" color="neutral" variant="ghost" class="composer-attachment touch-control" aria-label="Anhang hinzufügen – demnächst verfügbar" />
        <div class="flex-1" />
        <ChatModelMenu v-model="model" :busy="busy" compact label="Modell im Eingabefeld auswählen" />
        <UChatPromptSubmit
          :status="busy ? (streaming ? 'streaming' : 'submitted') : 'ready'" :disabled="!busy && (!text.trim() || tooLong || modelUnavailable)"
          color="neutral" variant="solid" streaming-color="neutral" streaming-variant="solid" submitted-color="neutral" submitted-variant="solid"
          :aria-label="busy ? (cancellationRequested ? 'Abbruch läuft' : 'Antwort stoppen') : 'Nachricht senden'"
          :aria-disabled="cancellationRequested" class="composer-submit touch-control rounded-full" @stop="emit('stop')"
        />
      </template>
    </UChatPrompt>
    <p v-if="tooLong" role="status" class="mt-2 text-center text-xs text-error">Die Nachricht darf höchstens {{ MAX_MESSAGE_LENGTH.toLocaleString('de-DE') }} Zeichen enthalten.</p>
  </div>
</template>
