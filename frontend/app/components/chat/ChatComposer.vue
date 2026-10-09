<script setup lang="ts">
import { computed, ref } from 'vue'
import { CHAT_MODELS } from '../../composables/useModelSelection'
import type { ChatModelId } from '../../composables/useModelSelection'
import { MAX_MESSAGE_LENGTH } from '../../lib/chat/types'

const props = defineProps<{ busy: boolean, streaming: boolean, cancellationRequested: boolean }>()
const text = defineModel<string>({ required: true })
const model = defineModel<ChatModelId>('model', { required: true })
const emit = defineEmits<{ send: [text: string], stop: [] }>()
const prompt = ref<{ textareaRef: HTMLTextAreaElement | undefined } | null>(null)
const tooLong = computed(() => text.value.length > MAX_MESSAGE_LENGTH)
function submit(): void {
  if (props.busy || !text.value.trim() || tooLong.value) return
  emit('send', text.value)
}
defineExpose({ focus: () => prompt.value?.textareaRef?.focus({ preventScroll: true }) })
</script>

<template>
  <div class="composer-container">
    <UChatPrompt
      ref="prompt" v-model="text" aria-label="Nachricht" placeholder="Frag noris AI …" :autofocus="false" :rows="2"
      :maxrows="8" :maxlength="MAX_MESSAGE_LENGTH * 2" class="chat-composer" :ui="{ base: 'text-base leading-6 max-h-48 overflow-y-auto', footer: 'items-center' }"
      @submit="submit"
    >
      <template #footer>
        <UButton disabled icon="i-lucide-plus" color="neutral" variant="ghost" class="touch-control" aria-label="Anhang hinzufügen – demnächst verfügbar" />
        <USelectMenu v-model="model" :items="[...CHAT_MODELS]" value-key="id" :search-input="false" :disabled="busy" variant="ghost" color="neutral" aria-label="Modell im Eingabefeld auswählen" class="max-w-48" :ui="{ base: 'min-h-11' }" />
        <div class="flex-1" />
        <UChatPromptSubmit
          :status="busy ? (streaming ? 'streaming' : 'submitted') : 'ready'" :disabled="!text.trim() || tooLong"
          :aria-label="busy ? (cancellationRequested ? 'Abbruch läuft' : 'Antwort stoppen') : 'Nachricht senden'"
          :aria-disabled="cancellationRequested" class="touch-control rounded-full" @stop="emit('stop')"
        />
      </template>
    </UChatPrompt>
    <p v-if="tooLong" role="status" class="mt-2 text-center text-xs text-error">Die Nachricht darf höchstens {{ MAX_MESSAGE_LENGTH.toLocaleString('de-DE') }} Zeichen enthalten.</p>
  </div>
</template>
