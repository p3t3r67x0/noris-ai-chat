import { onMounted, onUnmounted, ref } from 'vue'
import { getReadiness } from '../lib/api'

export type ServiceHealth = 'checking' | 'healthy' | 'unavailable'

export function useServiceHealth() {
  const status = ref<ServiceHealth>('checking')
  let controller: AbortController | undefined

  async function refresh(): Promise<void> {
    controller?.abort()
    const request = new AbortController()
    controller = request
    status.value = 'checking'
    try {
      await getReadiness(request.signal)
      if (!request.signal.aborted) status.value = 'healthy'
    }
    catch {
      if (!request.signal.aborted) status.value = 'unavailable'
    }
  }

  onMounted(refresh)
  onUnmounted(() => controller?.abort())
  return { status, refresh }
}
