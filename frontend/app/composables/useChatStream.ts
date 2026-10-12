import { computed, ref } from 'vue'
import { isBusy } from '../lib/chat/types'
import { CHAT_LIMITS } from '../lib/chat/limits'
import type { ChatRequest, ChatTransport, GenerationStatus } from '../lib/chat/types'
import { normalizeAppError } from '../lib/notifications/errors'
import type { ErrorContext, ErrorDiagnostics } from '../lib/notifications/errors'
import { TransportError } from '../lib/chat/realTransport'

export interface StreamCallbacks {
  delta: (text: string) => void
  status: (status: Exclude<GenerationStatus, 'idle'>) => void
  failure?: (code: string, message: string, diagnostics?: ErrorDiagnostics) => void
  replace?: (text: string) => void
  continuation?: (count: number) => void
}

export function useChatStream(transport: ChatTransport) {
  const status = ref<GenerationStatus>('idle')
  const error = ref<string | null>(null)
  const errorCode = ref<string | null>(null)
  const errorRequestId = ref<string | null>(null)
  const context = ref<ErrorContext>({ operation: 'generation' })
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
    errorRequestId.value = null
    context.value = { operation: 'generation', conversationId: request.conversationId, generationId: request.generationId, ...(request.assistantMessageId ? { resourceId: request.assistantMessageId } : {}) }
    cancellationRequested.value = false
    callbacks.status('submitting')
    let sequence = 0
    let length = request.operation === 'continue' ? (request.messages.at(-1)?.content.length ?? 0) : 0
    const maxResponseChars = CHAT_LIMITS.max_response_chars
    const transition = (next: Exclude<GenerationStatus, 'idle'>) => { status.value = next; callbacks.status(next) }
    const failure = (cause: unknown) => {
      const normalized = normalizeAppError(cause, context.value)
      error.value = normalized.message; errorCode.value = normalized.code; errorRequestId.value = normalized.diagnostics.requestId
      callbacks.failure?.(normalized.code, normalized.message, normalized.diagnostics)
    }
    try {
      for await (const event of transport.stream(request, signal)) {
        if (!isBusy(status.value)) break
        if (!Number.isSafeInteger(event.seq) || event.seq < (event.type === 'response.snapshot' ? 0 : 1)) throw new TransportError('INVALID_RESPONSE')
        if (event.type === 'response.snapshot') {
          if (event.seq < sequence) continue
          if (event.content.length > maxResponseChars) throw new TransportError('RESPONSE_SIZE_LIMIT')
          sequence = event.seq
          length = event.content.length
          callbacks.replace?.(event.content)
          if (event.continuationCount !== undefined) callbacks.continuation?.(event.continuationCount)
          if (event.code && event.message) {
            failure(event)
          }
          else if (event.status === 'failed') failure({ code: 'STREAM_INTERRUPTED', requestId: event.requestId })
          transition(event.status)
          if (!isBusy(status.value)) break
          continue
        }
        if (event.seq <= sequence) continue
        if (event.seq !== sequence + 1) throw new TransportError('STREAM_INTERRUPTED')
        sequence = event.seq
        if (signal.aborted && event.type !== 'response.cancelled') continue
        if (event.continuationCount !== undefined) callbacks.continuation?.(event.continuationCount)
        if ('content' in event && event.content !== undefined) {
          if (event.content.length > maxResponseChars) throw new TransportError('RESPONSE_SIZE_LIMIT')
          length = event.content.length
          callbacks.replace?.(event.content)
        }
        switch (event.type) {
          case 'response.started':
            if (status.value !== 'submitting') throw new TransportError('INVALID_RESPONSE')
            transition('streaming')
            break
          case 'response.output_text.delta':
            if (currentStatus() !== 'streaming') throw new TransportError('INVALID_RESPONSE')
            length += event.delta.length
            if (length > maxResponseChars) {
              throw new TransportError('RESPONSE_SIZE_LIMIT')
            }
            callbacks.delta(event.delta)
            break
          case 'response.completed': transition('completed'); break
          case 'response.incomplete':
            if (event.code && event.message) {
              failure(event)
            }
            transition('incomplete'); break
          case 'response.cancelled': transition('cancelled'); break
          case 'response.failed':
            failure(event)
            transition('failed'); break
        }
        if (!isBusy(status.value)) break
      }
      if (isBusy(status.value)) {
        if (signal.aborted) transition('cancelled')
        else throw new TransportError('STREAM_INTERRUPTED')
      }
    }
    catch (cause) {
      if (!isBusy(status.value)) return true
      if (signal.aborted) transition('cancelled')
      else {
        failure(cause)
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

  return { status, error, errorCode, errorRequestId, context, busy, cancellationRequested, start, stop }
}
