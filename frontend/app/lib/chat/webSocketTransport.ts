import type { ChatWsCommand, ChatWsEvent } from '../../types/generated/chat-ws'
import type { ChatTransport, StreamEvent } from './types'
import { ChatBackend } from './backend'
import { TransportError } from './realTransport'

export function createWebSocketTransport(options: { backend?: ChatBackend, url?: string, socket?: typeof WebSocket } = {}): ChatTransport {
  const backend = options.backend ?? new ChatBackend()
  let current: WebSocket | null = null
  let disposed = false
  let opening: Promise<WebSocket> | undefined
  const Socket = options.socket ?? globalThis.WebSocket
  let lastSeen = Date.now()
  let heartbeat: ReturnType<typeof setInterval> | undefined
  const send = (socket: WebSocket, value: ChatWsCommand) => socket.send(JSON.stringify(value))

  function connect(): Promise<WebSocket> {
    opening ??= openSocket().finally(() => { opening = undefined })
    return opening
  }

  async function openSocket(): Promise<WebSocket> {
    if (current?.readyState === Socket.OPEN) return current
    if (disposed) throw new TransportError('NETWORK_ERROR')
    const ticket = await backend.request<{ ticketId: string }>('/chat/ws-ticket', 'POST', {})
    const url = options.url ?? `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/v1/chat/ws`
    const socket = new Socket(url, ['noris-chat.v1', `ticket.${ticket.ticketId}`])
    current = socket
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => { socket.close(); reject(new TransportError('NETWORK_ERROR')) }, 10_000)
      socket.addEventListener('open', () => { clearTimeout(timer); resolve() }, { once: true })
      socket.addEventListener('error', () => { clearTimeout(timer); reject(new TransportError('NETWORK_ERROR')) }, { once: true })
    })
    lastSeen = Date.now()
    socket.addEventListener('message', (message) => {
      lastSeen = Date.now()
      try {
        const event = JSON.parse(String(message.data)) as ChatWsEvent
        if (event.version !== 1) return
        if (event.type === 'chat.conversation.updated') backend.remember(event.conversation)
      }
      catch { socket.close(1002) }
    })
    clearInterval(heartbeat)
    heartbeat = setInterval(() => {
      if (socket.readyState !== Socket.OPEN) return
      if (Date.now() - lastSeen > 90_000) socket.close()
      else send(socket, { version: 1, type: 'chat.ping' })
    }, 25_000)
    return socket
  }

  return {
    backend,
    async connect() { await connect() },
    dispose() { disposed = true; clearInterval(heartbeat); current?.close() },
    async *stream(request, signal) {
      if (!request.input || !request.assistantMessageId || !request.conversation) throw new TransportError('INVALID_RESPONSE')
      const version = request.resume ? 1 : await backend.ensure(request.conversation)
      let sent = request.resume === true
      let received = 0
      let reconnects = 0
      while (!disposed) {
        let socket: WebSocket
        try { socket = await connect() }
        catch (error) {
          if (!sent || reconnects++ >= 6) throw error
          await new Promise(resolve => setTimeout(resolve, Math.min(5000, 250 * 2 ** reconnects)))
          continue
        }
        const events: Array<ChatWsEvent | null> = []
        let wake: (() => void) | undefined
        let protocolError = false
        const onMessage = (message: MessageEvent) => {
          try {
            if (typeof message.data !== 'string' || message.data.length > 8_388_608) throw new Error()
            const value = JSON.parse(message.data) as ChatWsEvent
            if (value.version !== 1 || typeof value.type !== 'string') throw new Error()
            if (events.length >= 256) { socket.close(1013); return }
            events.push(value); wake?.()
          }
          catch { protocolError = true; socket.close(1002); wake?.() }
        }
        const onClose = () => { events.push(null); wake?.() }
        const cancel = () => { if (socket.readyState === Socket.OPEN) send(socket, { version: 1, type: 'chat.cancel', generationId: request.generationId }) }
        socket.addEventListener('message', onMessage)
        socket.addEventListener('close', onClose)
        signal.addEventListener('abort', cancel)
        try {
          if (sent && (received > 0 || request.resume)) send(socket, { version: 1, type: 'chat.resume', generationId: request.generationId, lastReceivedSeq: received })
          else {
            if (signal.aborted) return
            send(socket, {
              version: 1, type: 'chat.generate', requestId: request.generationId, conversationId: request.conversationId,
              inputMessageId: request.inputMessageId, assistantMessageId: request.assistantMessageId,
              conversationVersion: version, modelId: request.modelId, attempt: request.attempt,
              content: request.input.content, parentMessageId: request.input.parentMessageId,
              operation: request.operation ?? 'generate',
              ...(request.sourceAssistantMessageId ? { sourceAssistantMessageId: request.sourceAssistantMessageId } : {}),
              ...(request.input.editedFromMessageId ? { editedFromMessageId: request.input.editedFromMessageId } : {}),
            })
            sent = true
          }
          if (signal.aborted) cancel()
          while (true) {
            if (!events.length) await new Promise<void>(resolve => { wake = resolve })
            wake = undefined
            if (protocolError) throw new TransportError('INVALID_RESPONSE')
            const event = events.shift()
            if (event === null) break
            if (!event) continue
            if (event.type === 'chat.error' && (!event.requestId || event.requestId === request.generationId)) throw new TransportError(event.code, event.message)
            if (!('generationId' in event) || event.generationId !== request.generationId) continue
            if ('conversationId' in event && (event.conversationId !== request.conversationId || ('messageId' in event && event.messageId !== request.assistantMessageId))) throw new TransportError('INVALID_RESPONSE')
            if (event.type === 'chat.resume.snapshot') {
              if (!Number.isSafeInteger(event.lastSequence) || event.lastSequence < received || typeof event.content !== 'string') throw new TransportError('INVALID_RESPONSE')
              received = event.lastSequence
              const status = event.status === 'queued' ? 'submitting' : event.status === 'running' ? 'streaming' : event.status === 'interrupted' ? 'failed' : event.status
              yield { type: 'response.snapshot', seq: received, content: event.content, status }
              if (status !== 'submitting' && status !== 'streaming') return
              continue
            }
            if (!('seq' in event)) continue
            if (!Number.isSafeInteger(event.seq) || event.seq < 1) throw new TransportError('INVALID_RESPONSE')
            if (event.seq <= received) continue
            if (event.seq !== received + 1) { socket.close(); break }
            received = event.seq
            let output: StreamEvent
            switch (event.type) {
              case 'chat.generation.started': output = { type: 'response.started', seq: received }; break
              case 'chat.generation.delta':
                if (typeof event.delta !== 'string') throw new TransportError('INVALID_RESPONSE')
                output = { type: 'response.output_text.delta', seq: received, delta: event.delta }; break
              case 'chat.generation.completed': output = { type: 'response.completed', seq: received }; break
              case 'chat.generation.incomplete': output = { type: 'response.incomplete', seq: received, reason: 'output_limit' }; break
              case 'chat.generation.cancelled': output = { type: 'response.cancelled', seq: received }; break
              case 'chat.generation.failed': output = { type: 'response.failed', seq: received, code: event.code, message: event.message }; break
              case 'chat.generation.interrupted': output = { type: 'response.failed', seq: received, code: 'INTERRUPTED', message: 'Die Generierung wurde unterbrochen. Der gespeicherte Antwortstand bleibt erhalten.' }; break
              default: throw new TransportError('INVALID_RESPONSE')
            }
            yield output
            if (output.type === 'response.completed' || output.type === 'response.incomplete' || output.type === 'response.cancelled' || output.type === 'response.failed') return
          }
        }
        finally { socket.removeEventListener('message', onMessage); socket.removeEventListener('close', onClose); signal.removeEventListener('abort', cancel) }
        if (reconnects++ >= 6) throw new TransportError('NETWORK_ERROR', 'Die Verbindung konnte nicht wiederhergestellt werden. Lade den Chat neu, um den gespeicherten Stand abzurufen.')
        await new Promise(resolve => setTimeout(resolve, Math.min(5000, 250 * 2 ** reconnects)))
      }
    },
  }
}
