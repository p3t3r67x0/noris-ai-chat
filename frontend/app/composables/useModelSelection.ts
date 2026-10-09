import { onMounted, ref, watch } from 'vue'

export const CHAT_MODELS = [
  { id: 'balanced', label: 'noris Balanced', description: 'Für den Alltag' },
  { id: 'reasoning', label: 'noris Reasoning', description: 'Für komplexe Fragen' },
  { id: 'fast', label: 'noris Fast', description: 'Für schnelle Ideen' },
] as const

export type ChatModelId = typeof CHAT_MODELS[number]['id']

export function isChatModelId(value: unknown): value is ChatModelId {
  return CHAT_MODELS.some(model => model.id === value)
}

export function useModelSelection() {
  const modelId = ref<ChatModelId>('balanced')
  onMounted(() => {
    try {
      const saved = window.localStorage.getItem('noris-ai:model')
      if (isChatModelId(saved)) modelId.value = saved
    }
    catch { /* The default model remains usable without browser storage. */ }
  })
  watch(modelId, (value) => {
    if (!import.meta.client) return
    try { window.localStorage.setItem('noris-ai:model', value) }
    catch { /* Model selection does not depend on persistence. */ }
  })
  return { modelId, models: CHAT_MODELS }
}
