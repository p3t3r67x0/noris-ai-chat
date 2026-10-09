import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { responseError } from '../lib/chat/realTransport'

const MOCK_MODELS = [
  { id: 'balanced', label: 'noris Balanced', description: 'Für den Alltag' },
  { id: 'reasoning', label: 'noris Reasoning', description: 'Für komplexe Fragen' },
  { id: 'fast', label: 'noris Fast', description: 'Für schnelle Ideen' },
]

export interface ChatModel { id: string, label: string, description: string, category?: string, virtual?: boolean, disabled?: boolean }
export const CHAT_MODELS = reactive<ChatModel[]>(MOCK_MODELS.map(model => ({ ...model })))
export type ChatModelId = string
export function isChatModelId(value: unknown): value is ChatModelId {
  return CHAT_MODELS.some(model => model.id === value && !model.disabled)
}

export function useModelSelection(options: { mode?: 'mock' | 'real', fetcher?: typeof fetch } = {}) {
  const real = options.mode === 'real'
  CHAT_MODELS.splice(0, CHAT_MODELS.length, ...(real ? [] : MOCK_MODELS.map(model => ({ ...model }))))
  const modelId = ref<ChatModelId>(real ? '' : 'balanced')
  const error = ref<string | null>(null)
  const notice = ref<string | null>(null)
  const loading = ref(real)
  const stale = ref(false)
  const fallbackId = ref<string | null>(null)
  const controller = new AbortController()
  let timer: ReturnType<typeof setTimeout> | undefined
  let initial = true
  let pending: Promise<void> | undefined
  const canSend = computed(() => !loading.value && !error.value && !stale.value && isChatModelId(modelId.value))

  async function load(): Promise<void> {
    loading.value = true
    clearTimeout(timer)
    try {
      const response = await (options.fetcher ?? globalThis.fetch)('/api/v1/llm/models', { credentials: 'same-origin', signal: controller.signal, headers: { Accept: 'application/json' } })
      if (!response.ok) throw await responseError(response)
      const catalog: unknown = await response.json()
      if (!catalog || typeof catalog !== 'object' || !('models' in catalog) || !Array.isArray(catalog.models) || !('default_model' in catalog) || (catalog.default_model !== null && typeof catalog.default_model !== 'string')) throw new Error('Ungültige Modellkonfiguration')
      const isStale = 'status' in catalog && catalog.status === 'stale'
      const models: ChatModel[] = []
      for (const value of catalog.models as unknown[]) {
        if (!value || typeof value !== 'object' || !('id' in value) || typeof value.id !== 'string' || !('name' in value) || typeof value.name !== 'string' || !('available' in value) || !('streaming' in value)) throw new Error('Ungültige Modellkonfiguration')
        if (value.streaming === true && (value.available === true || isStale)) models.push({
          id: value.id, label: value.name, description: 'description' in value && typeof value.description === 'string' ? value.description : '',
          category: 'category' in value && typeof value.category === 'string' ? value.category : '',
          virtual: 'virtual' in value && value.virtual === true, disabled: isStale || value.available !== true,
        })
      }
      if ((catalog.default_model !== null && !models.some(model => model.id === catalog.default_model)) || new Set(models.map(model => model.id)).size !== models.length) throw new Error('Ungültige Modellkonfiguration')
      if (controller.signal.aborted) return
      CHAT_MODELS.splice(0, CHAT_MODELS.length, ...models)
      error.value = null
      stale.value = isStale
      fallbackId.value = isStale ? null : catalog.default_model
      if (initial && !modelId.value) modelId.value = catalog.default_model ?? ''
      initial = false
      notice.value = isStale ? 'Der Modellkatalog ist veraltet. Neue Anfragen sind bis zur Prüfung gesperrt.'
        : !models.length ? 'Für diesen Zugang sind derzeit keine Chatmodelle verfügbar.'
            : !isChatModelId(modelId.value) ? 'Dein gewähltes Modell ist nicht mehr verfügbar. Wähle ein verfügbares Modell; dein Chat und Entwurf bleiben erhalten.' : null
      if (!isStale && 'expires_in_seconds' in catalog && typeof catalog.expires_in_seconds === 'number' && catalog.expires_in_seconds > 0) {
        timer = setTimeout(() => { void refresh() }, Math.max(1000, catalog.expires_in_seconds * 1000))
      }
    }
    catch (cause) {
      if (!controller.signal.aborted) {
        error.value = cause instanceof Error ? cause.message : 'Modelle konnten nicht geladen werden.'
        CHAT_MODELS.splice(0)
        fallbackId.value = null
      }
    }
    finally { loading.value = false }
  }
  function refresh(): Promise<void> {
    if (!real || controller.signal.aborted) return Promise.resolve()
    pending ??= load().finally(() => { pending = undefined })
    return pending
  }
  function chooseFallback(): void {
    if (fallbackId.value && isChatModelId(fallbackId.value)) modelId.value = fallbackId.value
  }
  function onFocus(): void { void refresh() }
  onMounted(async () => {
    try {
      const saved = window.localStorage.getItem('noris-ai:model')
      if (saved && (real || isChatModelId(saved))) modelId.value = saved
    }
    catch { /* Selection works without browser storage. */ }
    if (real) { window.addEventListener('focus', onFocus); await refresh() }
  })
  onUnmounted(() => { controller.abort(); clearTimeout(timer); window.removeEventListener('focus', onFocus) })
  watch(modelId, (value) => {
    if (isChatModelId(value)) notice.value = null
    if (!import.meta.client || !isChatModelId(value)) return
    try { window.localStorage.setItem('noris-ai:model', value) }
    catch { /* Persistence is optional. */ }
  })
  return { modelId, models: CHAT_MODELS, error, notice, loading, stale, canSend, fallbackId, refresh, chooseFallback }
}
