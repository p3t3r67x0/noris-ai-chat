<script setup lang="ts">
import { computed, ref } from 'vue'
import { CHAT_MODELS } from '../../composables/useModelSelection'
import type { ChatModelId } from '../../composables/useModelSelection'
import { chatLimits } from '../../lib/chat/limits'

const props = defineProps<{ busy: boolean, streaming: boolean, cancellationRequested: boolean, inputError?: string | null }>()
const text = defineModel<string>({ required: true })
const model = defineModel<ChatModelId>('model', { required: true })
const emit = defineEmits<{ send: [text: string], stop: [] }>()
const prompt = ref<{ textareaRef: HTMLTextAreaElement | undefined } | null>(null)
const tooLong = computed(() => text.value.length > chatLimits.max_message_chars)
const models = computed(() => CHAT_MODELS.map(item => ({ ...item, label: item.label.replace('noris ', '') })))
function submit(): void {
  if (props.busy || props.inputError || !text.value.trim() || tooLong.value) return
  emit('send', text.value)
}
defineExpose({ focus: () => prompt.value?.textareaRef?.focus({ preventScroll: true }) })
</script>

<template>
  <div class="composer-container">
    <UChatPrompt
      ref="prompt" v-model="text" aria-label="Nachricht" placeholder="Frag noris AI …" :autofocus="false" :rows="1"
      variant="naked" color="neutral" :maxrows="8" class="chat-composer"
      :ui="{ root: 'gap-0 p-0', base: 'composer-input overflow-y-auto', footer: 'composer-toolbar' }"
      @submit="submit"
    >
      <template #footer>
        <UButton disabled icon="i-lucide-plus" color="neutral" variant="ghost" class="composer-attachment touch-control" aria-label="Anhang hinzufügen – demnächst verfügbar" />
        <div class="flex-1" />
        <USelectMenu v-model="model" :items="models" value-key="id" :search-input="false" :disabled="busy" variant="ghost" color="neutral" aria-label="Modell im Eingabefeld auswählen" class="composer-model" :ui="{ base: 'min-h-11', content: 'min-w-48' }" />
        <UChatPromptSubmit
          :status="busy ? (streaming ? 'streaming' : 'submitted') : 'ready'" :disabled="!text.trim() || tooLong || !!inputError"
          color="neutral" variant="solid" streaming-color="neutral" streaming-variant="solid" submitted-color="neutral" submitted-variant="solid"
          :aria-label="busy ? (cancellationRequested ? 'Abbruch läuft' : 'Antwort stoppen') : 'Nachricht senden'"
          :aria-disabled="cancellationRequested" class="composer-submit touch-control rounded-full" @stop="emit('stop')"
        />
      </template>
    </UChatPrompt>
    <p v-if="tooLong" role="status" class="mt-2 text-center text-xs text-error">Die Nachricht darf höchstens {{ chatLimits.max_message_chars.toLocaleString('de-DE') }} Zeichen enthalten.</p>
  </div>
</template>
