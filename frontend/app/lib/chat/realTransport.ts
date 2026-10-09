import type { ChatTransport, StreamEvent, ConversationTitleResponse } from './types'
import { validGeneratedTitle } from './titles'

const messages: Record<string, string> = {
  ACCESS_DENIED: 'Bitte öffne /api/v1/llm/models und melde dich für den Modellzugriff an.',
  LLM_DISABLED: 'Die Modellanbindung ist nicht freigeschaltet.',
  RATE_LIMIT: 'Zu viele Modellanfragen. Bitte versuche es später erneut.',
  TIMEOUT: 'Die Modellantwort hat zu lange gedauert.',
  STREAM_INTERRUPTED: 'Die Verbindung endete vor dem Abschluss der Antwort.',
  INVALID_RESPONSE: 'Die Modellantwort konnte nicht korrekt übertragen werden.',
  NETWORK_ERROR: 'Der Modelldienst ist derzeit nicht erreichbar.',
  REQUEST_FAILED: 'Die Modellanfrage konnte nicht verarbeitet werden.',
}

export class TransportError extends Error {
  constructor(readonly code: string, message?: string) {
    super(message ?? messages[code] ?? messages.REQUEST_FAILED)
  }
}

export async function responseError(response: Response): Promise<TransportError> {
  // Backend errors are sanitized; do not surface arbitrary proxy/HTML response bodies.
  try {
    const payload: unknown = await response.json()
    if (payload && typeof payload === 'object' && 'error' in payload) {
      const error = payload.error
      if (error && typeof error === 'object' && 'code' in error && typeof error.code === 'string') {
        if (error.code === 'ACCESS_DENIED') return new TransportError(error.code)
        if ('message' in error && typeof error.message === 'string' && error.message.length <= 1000) return new TransportError(error.code, error.message)
      }
    }
  }
  catch { /* Unknown errors use a fixed message. */ }
  return new TransportError(response.status === 401 ? 'ACCESS_DENIED' : 'REQUEST_FAILED')
}

export interface SSEFrame { event: string | null, data: string }
export class SSEFrames {
  private buffer = ''
  private data: string[] = []
  private event: string | null = null
  private size = 0
  private skipLF = false

  feed(text: string): SSEFrame[] {
    if (text && this.skipLF) {
      if (text.startsWith('\n')) text = text.slice(1)
      this.skipLF = false
    }
    this.buffer += text
    const frames: SSEFrame[] = []
    let match: RegExpExecArray | null
    while ((match = /\r\n|\r|\n/.exec(this.buffer))) {
      this.skipLF = match[0] === '\r' && match.index + 1 === this.buffer.length
      const line = this.buffer.slice(0, match.index)
      this.buffer = this.buffer.slice(match.index + match[0].length)
      if (line.length > 65_536) throw new TransportError('INVALID_RESPONSE')
      if (!line) {
        if (this.data.length) frames.push({ event: this.event, data: this.data.join('\n') })
        this.data = []; this.event = null; this.size = 0
      }
      else if (line.startsWith('data:')) {
        this.size += line.length
        if (this.size > 65_536) throw new TransportError('INVALID_RESPONSE')
        this.data.push(line.slice(5).replace(/^ /, ''))
      }
      else if (line.startsWith('event:')) this.event = line.slice(6).replace(/^ /, '')
    }
    if (this.buffer.length > 65_536) throw new TransportError('INVALID_RESPONSE')
    return frames
  }

  get incomplete(): boolean { return Boolean(this.buffer || this.data.length) }
}

export function parseStreamEvent(frame: SSEFrame): StreamEvent {
  let value: unknown
  try { value = JSON.parse(frame.data) }
  catch { throw new TransportError('INVALID_RESPONSE') }
  if (!value || typeof value !== 'object' || !('seq' in value) || !Number.isSafeInteger(value.seq) || Number(value.seq) < 1 || !('type' in value) || typeof value.type !== 'string' || (frame.event !== null && frame.event !== value.type)) throw new TransportError('INVALID_RESPONSE')
  switch (value.type) {
    case 'response.started': case 'response.completed': case 'response.cancelled': break
    case 'response.output_text.delta':
      if (!('delta' in value) || typeof value.delta !== 'string') throw new TransportError('INVALID_RESPONSE')
      break
    case 'response.failed':
      if (!('code' in value) || typeof value.code !== 'string' || !('message' in value) || typeof value.message !== 'string' || value.message.length > 1000) throw new TransportError('INVALID_RESPONSE')
      break
    default: throw new TransportError('INVALID_RESPONSE')
  }
  return value as StreamEvent
}

export function createRealTransport(options: { fetcher?: typeof fetch, timeoutMs?: number } = {}): ChatTransport {
  const fetcher = options.fetcher ?? globalThis.fetch
  return {
    async generateTitle(request, signal) {
      const response = await fetcher('/api/v1/llm/conversation-title', {
        method: 'POST', credentials: 'same-origin', signal,
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      })
      if (!response.ok) throw await responseError(response)
      if (response.headers.get('Content-Type')?.split(';')[0]?.trim() !== 'application/json') throw new TransportError('INVALID_RESPONSE')
      const result: unknown = await response.json()
      if (!result || typeof result !== 'object' || !('title' in result) || !('conversationId' in result) || !('inputMessageId' in result) || result.conversationId !== request.conversationId || result.inputMessageId !== request.inputMessageId || !validGeneratedTitle(result.title)) throw new TransportError('INVALID_RESPONSE')
      return result as ConversationTitleResponse
    },
    async *stream(request, signal) {
      const controller = new AbortController()
      const abort = () => controller.abort()
      let timedOut = false
      let sequence = 0
      let reader: ReadableStreamDefaultReader<Uint8Array> | undefined
      signal.addEventListener('abort', abort, { once: true })
      if (signal.aborted) controller.abort()
      const timer = setTimeout(() => { timedOut = true; controller.abort() }, options.timeoutMs ?? 135_000)
      try {
        if (signal.aborted) { yield { seq: 1, type: 'response.cancelled' }; return }
        const response = await fetcher('/api/v1/llm/chat', {
          method: 'POST', credentials: 'same-origin', signal: controller.signal,
          headers: { Accept: 'text/event-stream', 'Content-Type': 'application/json' },
          body: JSON.stringify(request),
        })
        if (!response.ok) throw await responseError(response)
        if (!response.body || response.headers.get('Content-Type')?.split(';')[0]?.trim() !== 'text/event-stream') throw new TransportError('INVALID_RESPONSE')
        reader = response.body.getReader()
        const decoder = new TextDecoder('utf-8', { fatal: true })
        const frames = new SSEFrames()
        let received = 0
        while (true) {
          const { value, done } = await reader.read()
          if (signal.aborted) { yield { seq: sequence + 1, type: 'response.cancelled' }; return }
          if (done) {
            frames.feed(decoder.decode())
            throw new TransportError(frames.incomplete ? 'INVALID_RESPONSE' : 'STREAM_INTERRUPTED')
          }
          received += value.byteLength
          if (received > 4_194_304) throw new TransportError('INVALID_RESPONSE')
          for (const frame of frames.feed(decoder.decode(value, { stream: true }))) {
            const event = parseStreamEvent(frame)
            if (event.seq !== sequence + 1) throw new TransportError('INVALID_RESPONSE')
            sequence = event.seq
            yield event
            if (['response.completed', 'response.cancelled', 'response.failed'].includes(event.type)) return
          }
        }
      }
      catch (error) {
        if (signal.aborted) yield { seq: sequence + 1, type: 'response.cancelled' }
        else {
          const failure = timedOut ? new TransportError('TIMEOUT') : error instanceof TransportError ? error : new TransportError(error instanceof TypeError ? 'NETWORK_ERROR' : 'INVALID_RESPONSE')
          yield { seq: sequence + 1, type: 'response.failed', code: failure.code, message: failure.message }
        }
      }
      finally {
        clearTimeout(timer)
        signal.removeEventListener('abort', abort)
        controller.abort()
        try { await reader?.cancel() }
        catch { /* The aborted fetch may already have closed its reader. */ }
        reader?.releaseLock()
      }
    },
  }
}
