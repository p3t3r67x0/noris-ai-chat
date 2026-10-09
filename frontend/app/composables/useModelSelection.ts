import { onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { responseError } from '../lib/chat/realTransport'

const MOCK_MODELS = [
  { id: 'balanced', label: 'noris Balanced', description: 'Für den Alltag' },
  { id: 'reasoning', label: 'noris Reasoning', description: 'Für komplexe Fragen' },
  { id: 'fast', label: 'noris Fast', description: 'Für schnelle Ideen' },
]

export interface ChatModel { id: string, label: string, description: string }
// Keep this array identity: existing Header/Composer imports react to its contents.
export const CHAT_MODELS = reactive<ChatModel[]>(MOCK_MODELS.map(model => ({ ...model })))

export type ChatModelId = string

export function isChatModelId(value: unknown): value is ChatModelId {
  return CHAT_MODELS.some(model => model.id === value)
}

export function useModelSelection(options: { mode?: 'mock' | 'real', fetcher?: typeof fetch } = {}) {
  const real = options.mode === 'real'
  CHAT_MODELS.splice(0, CHAT_MODELS.length, ...(real ? [] : MOCK_MODELS.map(model => ({ ...model }))))
  const modelId = ref<ChatModelId>(real ? '' : 'balanced')
  const error = ref<string | null>(null)
  const controller = new AbortController()
  onMounted(async () => {
    if (real) {
      try {
        const response = await (options.fetcher ?? globalThis.fetch)('/api/v1/llm/models', { credentials: 'same-origin', signal: controller.signal, headers: { Accept: 'application/json' } })
        if (!response.ok) throw await responseError(response)
        const catalog: unknown = await response.json()
        if (!catalog || typeof catalog !== 'object' || !('models' in catalog) || !Array.isArray(catalog.models) || !('default_model' in catalog) || typeof catalog.default_model !== 'string') throw new Error('Ungültige Modellkonfiguration')
        const models: ChatModel[] = []
        for (const value of catalog.models as unknown[]) {
          if (!value || typeof value !== 'object' || !('id' in value) || typeof value.id !== 'string' || !('name' in value) || typeof value.name !== 'string' || !('available' in value) || !('streaming' in value)) throw new Error('Ungültige Modellkonfiguration')
          if (value.available === true && value.streaming === true) models.push({ id: value.id, label: value.name, description: '' })
        }
        if (!models.some(model => model.id === catalog.default_model) || new Set(models.map(model => model.id)).size !== models.length) throw new Error('Ungültige Modellkonfiguration')
        if (controller.signal.aborted) return
        CHAT_MODELS.splice(0, CHAT_MODELS.length, ...models)
        modelId.value = catalog.default_model
      }
      catch (cause) {
        if (!controller.signal.aborted) error.value = cause instanceof Error ? cause.message : 'Modelle konnten nicht geladen werden.'
        return
      }
    }
    try {
      const saved = window.localStorage.getItem('noris-ai:model')
      if (isChatModelId(saved)) modelId.value = saved
    }
    catch { /* The default model remains usable without browser storage. */ }
  })
  onUnmounted(() => controller.abort())
  watch(modelId, (value) => {
    if (!import.meta.client) return
    try { window.localStorage.setItem('noris-ai:model', value) }
    catch { /* Model selection does not depend on persistence. */ }
  })
  return { modelId, models: CHAT_MODELS, error }
}
