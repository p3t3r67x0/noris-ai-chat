import { computed, ref } from 'vue'
import { isBusy } from '../lib/chat/types'
import { CHAT_LIMITS } from '../lib/chat/limits'
import type { ChatRequest, ChatTransport, GenerationStatus } from '../lib/chat/types'

export interface StreamCallbacks {
  delta: (text: string) => void
  status: (status: Exclude<GenerationStatus, 'idle'>) => void
  failure?: (code: string, message: string) => void
  replace?: (text: string) => void
}

export function useChatStream(transport: ChatTransport) {
  const status = ref<GenerationStatus>('idle')
  const error = ref<string | null>(null)
  const errorCode = ref<string | null>(null)
  const cancellationRequested = ref(false)
  const running = ref(false)
  const busy = computed(() => running.value)
  let controller: AbortController | null = null
  const currentStatus = (): GenerationStatus => status.value

  async function start(request: ChatRequest, callbacks: StreamCallbacks): Promise<boolean> {
    if (busy.value) return false
    running.value = true
    controller = new AbortController()
    const signal = controller.signal
    status.value = 'submitting'
    error.value = null
    errorCode.value = null
    cancellationRequested.value = false
    callbacks.status('submitting')
    let sequence = 0
    let length = request.operation === 'continue' ? (request.messages.at(-1)?.content.length ?? 0) : 0
    const maxResponseChars = CHAT_LIMITS.max_response_chars
    const transition = (next: Exclude<GenerationStatus, 'idle'>) => { status.value = next; callbacks.status(next) }
    try {
      for await (const event of transport.stream(request, signal)) {
        if (!isBusy(status.value)) break
        if (!Number.isSafeInteger(event.seq) || event.seq < (event.type === 'response.snapshot' ? 0 : 1)) throw new Error('Ungültige Ereignisfolge')
        if (event.type === 'response.snapshot') {
          if (event.seq < sequence) continue
          if (event.content.length > maxResponseChars) throw new Error('Die Antwort überschreitet die zulässige Länge.')
          sequence = event.seq
          length = event.content.length
          callbacks.replace?.(event.content)
          transition(event.status)
          if (!isBusy(status.value)) break
          continue
        }
        if (event.seq <= sequence) continue
        if (event.seq !== sequence + 1) throw new Error('Die Antwort wurde unvollständig übertragen.')
        sequence = event.seq
        if (signal.aborted && event.type !== 'response.cancelled') continue
        switch (event.type) {
          case 'response.started':
            if (status.value !== 'submitting') throw new Error('Die Antwort wurde mehrfach gestartet.')
            transition('streaming')
            break
          case 'response.output_text.delta':
            if (currentStatus() !== 'streaming') throw new Error('Text ohne gestartete Antwort')
            length += event.delta.length
            if (length > maxResponseChars) {
              errorCode.value = 'RESPONSE_SIZE_LIMIT'
              throw new Error('Die Antwort hat die konfigurierte Größenbegrenzung erreicht.')
            }
            callbacks.delta(event.delta)
            break
          case 'response.completed': transition('completed'); break
          case 'response.incomplete': transition('incomplete'); break
          case 'response.cancelled': transition('cancelled'); break
          case 'response.failed':
            error.value = event.message; errorCode.value = event.code
            callbacks.failure?.(event.code, event.message)
            transition('failed'); break
        }
        if (!isBusy(status.value)) break
      }
      if (isBusy(status.value)) {
        if (signal.aborted) transition('cancelled')
        else throw new Error('Die Verbindung endete vor dem Abschluss der Antwort.')
      }
    }
    catch (cause) {
      if (!isBusy(status.value)) return true
      if (signal.aborted) transition('cancelled')
      else {
        error.value = cause instanceof Error ? cause.message : 'Die Antwort konnte nicht geladen werden.'
        errorCode.value ??= 'STREAM_INTERRUPTED'
        callbacks.failure?.(errorCode.value, error.value)
        transition('failed')
      }
    }
    finally { controller = null; cancellationRequested.value = false; running.value = false }
    return true
  }

  function stop(): void {
    if (!busy.value || !controller) return
    cancellationRequested.value = true
    controller.abort()
  }

  return { status, error, errorCode, busy, cancellationRequested, start, stop }
}
