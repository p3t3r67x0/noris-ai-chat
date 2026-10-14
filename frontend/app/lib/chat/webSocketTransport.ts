import type { ChatWsCommand, ChatWsEvent } from '../../types/generated/chat-ws'
import type { ChatTransport, StreamEvent, ResearchView } from './types'
import { ChatBackend } from './backend'
import { TransportError } from './realTransport'
import { validateToolEvent } from './toolEvents'

export function createWebSocketTransport(options: { backend?: ChatBackend, url?: string, socket?: typeof WebSocket } = {}): ChatTransport {
  const backend = options.backend ?? new ChatBackend()
  let current: WebSocket | null = null
  let disposed = false
  let opening: Promise<WebSocket> | undefined
  const Socket = options.socket ?? globalThis.WebSocket
  let lastSeen = Date.now()
  let heartbeat: ReturnType<typeof setInterval> | undefined
  let reconnectTimer: ReturnType<typeof setTimeout> | undefined
  let backgroundReconnects = 0
  const toolScopes = new Map<string, string>()
  const toolSnapshots = new Map<string, number>()
  const streaming = new Set<string>()
  function scope(generationId: string, conversationId: string): void {
    toolScopes.delete(generationId)
    toolScopes.set(generationId, conversationId)
    if (toolScopes.size > 64) {
      const oldest = [...toolScopes.keys()].find(id => !streaming.has(id))!
      toolScopes.delete(oldest); toolSnapshots.delete(oldest)
    }
  }
  function parse(raw: unknown): ChatWsEvent {
    if (typeof raw !== 'string' || raw.length > 8_388_608) throw new TransportError('INVALID_RESPONSE')
    const value = JSON.parse(raw) as ChatWsEvent
    if (!value || value.version !== 1 || typeof value.type !== 'string') throw new TransportError('INVALID_RESPONSE')
    if (value.type === 'research.updated' && (value.eventVersion !== 1 || !['planning', 'searching', 'selecting', 'fetching', 'grounding', 'generating', 'completed', 'failed', 'cancelled', 'interrupted', 'skipped'].includes(value.state))) throw new TransportError('INVALID_RESPONSE')
    if (value.type.startsWith('tool.') && !validateToolEvent(value)) throw new TransportError('INVALID_RESPONSE')
    return value
  }
  const send = (socket: WebSocket, value: ChatWsCommand) => socket.send(JSON.stringify(value))

  function connect(): Promise<WebSocket> {
    opening ??= openSocket().finally(() => { opening = undefined })
    return opening
  }

  function reconnect(): void {
    if (disposed || reconnectTimer || backgroundReconnects >= 6) return
    reconnectTimer = setTimeout(() => {
      reconnectTimer = undefined
      if (disposed) return
      backgroundReconnects++
      void connect().catch(reconnect)
    }, Math.min(5000, 250 * 2 ** backgroundReconnects))
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
        const event = parse(message.data)
        if (event.type.startsWith('tool.')) {
          if (!validateToolEvent(event)) throw new TransportError('INVALID_RESPONSE')
          if (toolScopes.get(event.generationId) !== event.conversationId || backend.isDeleted(event.conversationId)) return
          const boundary = toolSnapshots.get(event.generationId) ?? -1
          if (event.type === 'tool.snapshot') {
            if (event.lastSequence < boundary) return
            toolSnapshots.set(event.generationId, event.lastSequence)
            for (const run of event.runs) backend.onToolState?.({ ...run, conversationId: event.conversationId, generationId: event.generationId })
          }
          else if (event.seq > boundary) backend.onToolState?.({ ...event.payload, conversationId: event.conversationId, generationId: event.generationId })
          return
        }
        if (event.type === 'chat.connected') {
          // Metadata events have no generation sequence and cannot be replayed.
          void backend.refreshMetadata().then(() => { backgroundReconnects = 0 }).catch(() => { socket.close() })
        }
        if (event.type === 'chat.conversation.updated') backend.remember(event.conversation)
        if (event.type === 'chat.conversation.deleted') {
          backend.forget(event.conversationId, event.conversationVersion)
          for (const [id, conversationId] of toolScopes) {
            if (conversationId === event.conversationId) { toolScopes.delete(id); toolSnapshots.delete(id) }
          }
        }
        if (event.type === 'chat.title.updated') {
          // Fetch the versioned authority so a late title event cannot undo a
          // manual rename or a newer update from another tab.
          void backend.request<Parameters<ChatBackend['remember']>[0]>(`/conversations/${event.conversationId}`).then(value => backend.remember(value)).catch(() => { socket.close() })
        }
        if (event.type === 'chat.message.created') backend.onMessage?.(event.message)
      }
      catch { socket.close(1002) }
    })
    for (const [generationId] of toolScopes) {
      if (!streaming.has(generationId)) send(socket, { version: 1, type: 'chat.resume', generationId, lastReceivedSeq: 0, toolEventVersion: 1, toolEventsOnly: true })
    }
    socket.addEventListener('close', reconnect, { once: true })
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
    async observeTools(conversationId, generationIds) {
      if (backend.isDeleted(conversationId)) return
      const fresh = [...new Set(generationIds)].filter(id => !streaming.has(id)).slice(-50)
      for (const id of fresh) scope(id, conversationId)
      if (!fresh.length) return
      const alreadyOpen = current?.readyState === Socket.OPEN
      const socket = await connect()
      if (alreadyOpen) for (const generationId of fresh) send(socket, { version: 1, type: 'chat.resume', generationId, lastReceivedSeq: 0, toolEventVersion: 1, toolEventsOnly: true })
    },
    dispose() { disposed = true; clearInterval(heartbeat); clearTimeout(reconnectTimer); current?.close() },
    async *stream(request, signal) {
      if (!request.input || !request.assistantMessageId || !request.conversation) throw new TransportError('INVALID_RESPONSE')
      const version = request.resume ? 1 : await backend.ensure(request.conversation)
      scope(request.generationId, request.conversationId)
      streaming.add(request.generationId)
      let sent = request.resume === true
      let researchObserved = Boolean(request.research || request.inheritedResearch)
      let researchLoadFailed = false
      const readResearch = async (): Promise<ResearchView | null> => {
        try {
          const view = await backend.request<ResearchView | null>(`/chat/conversations/${request.conversationId}/generations/${request.generationId}/research`)
          researchLoadFailed = view === null
          return view
        }
        catch { researchLoadFailed = true; return null }
      }
      let received = 0
      let reconnects = 0
      try {
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
              const value = parse(message.data)
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
            if (sent && (received > 0 || request.resume)) send(socket, { version: 1, type: 'chat.resume', generationId: request.generationId, lastReceivedSeq: received, toolEventVersion: 1, researchEventVersion: 1 })
            else {
              if (signal.aborted) return
              const attachmentIds = request.input.attachments?.filter(file => !request.input?.editedFromMessageId || file.messageId === request.input.id).map(file => file.id) ?? []
              send(socket, {
                version: 1, type: 'chat.generate', toolEventVersion: 1, researchEventVersion: 1, ...(request.research ? { research: request.research } : {}), requestId: request.generationId, conversationId: request.conversationId,
                inputMessageId: request.inputMessageId, assistantMessageId: request.assistantMessageId,
                conversationVersion: version, modelId: request.modelId, attempt: request.attempt,
                content: request.input.content, parentMessageId: request.input.parentMessageId,
                operation: request.operation ?? 'generate',
                ...(attachmentIds.length ? { attachmentIds } : {}),
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
              if (event.type === 'chat.error' && (!event.requestId || event.requestId === request.generationId)) throw new TransportError(event.code, undefined, event.requestId ?? null)
              if (!('generationId' in event) || event.generationId !== request.generationId) continue
              if ('conversationId' in event && (event.conversationId !== request.conversationId || ('messageId' in event && event.messageId !== request.assistantMessageId))) throw new TransportError('INVALID_RESPONSE')
              if (event.type === 'chat.resume.snapshot') {
                if (!Number.isSafeInteger(event.lastSequence) || event.lastSequence < received || typeof event.content !== 'string') throw new TransportError('INVALID_RESPONSE')
                received = event.lastSequence
                const status = event.status === 'queued' ? 'submitting' : event.status === 'running' ? 'streaming' : event.status === 'interrupted' ? 'failed' : event.status
                let research: ResearchView | null | undefined
                if (event.researchMode === 'web' || researchObserved) {
                  researchObserved = true
                  research = await readResearch()
                }
                yield { type: 'response.snapshot', ...(research ? { research } : {}), ...((research?.state ?? event.researchState) ? { researchState: (research?.state ?? event.researchState)! } : {}), researchLoadFailed, seq: received, content: event.content, status, continuationCount: event.continuationCount, code: event.code, message: event.message, requestId: request.generationId }
                if (status !== 'submitting' && status !== 'streaming') return
                continue
              }
              if (!('seq' in event)) continue
              if (!Number.isSafeInteger(event.seq) || event.seq < 1) throw new TransportError('INVALID_RESPONSE')
              if (event.seq <= received) continue
              if (event.seq !== received + 1) { socket.close(); break }
              received = event.seq
              if (validateToolEvent(event)) {
                yield { type: 'response.tool', seq: received, requestId: request.generationId }
                continue
              }
              if (event.type === 'research.updated') {
                researchObserved = true
                const view = ['generating', 'completed', 'failed', 'cancelled', 'interrupted'].includes(event.state) ? await readResearch() : undefined
                yield { type: 'response.research', seq: received, state: view?.state ?? event.state, researchLoadFailed, ...(view ? { research: view } : {}) }
                continue
              }
              let output: StreamEvent
              switch (event.type) {
                case 'chat.generation.started': output = { type: 'response.started', seq: received }; break
                case 'chat.generation.delta':
                  if (typeof event.delta !== 'string') throw new TransportError('INVALID_RESPONSE')
                  output = { type: 'response.output_text.delta', seq: received, delta: event.delta }; break
                case 'chat.generation.completed': output = { type: 'response.completed', seq: received, content: event.content }; break
                case 'chat.generation.incomplete': output = { type: 'response.incomplete', seq: received, reason: 'output_limit', content: event.content, code: event.code, message: event.message }; break
                case 'chat.generation.cancelled': output = { type: 'response.cancelled', seq: received, content: event.content }; break
                case 'chat.generation.failed': output = { type: 'response.failed', seq: received, code: event.code, message: event.message, content: event.content }; break
                case 'chat.generation.interrupted': output = { type: 'response.failed', seq: received, code: 'INTERRUPTED', message: 'Die Generierung wurde unterbrochen. Der gespeicherte Antwortstand bleibt erhalten.', content: event.content }; break
                default: throw new TransportError('INVALID_RESPONSE')
              }
              if (researchObserved && request.inheritedResearch && 'content' in output) {
                const view = await readResearch()
                if (view) output = { ...output, research: view } as StreamEvent
              }
              yield { ...output, ...((output.research?.state ?? ('researchState' in event ? event.researchState : null)) ? { researchState: (output.research?.state ?? ('researchState' in event ? event.researchState : null))! } : {}), researchLoadFailed, continuationCount: event.continuationCount, requestId: request.generationId }
              if (output.type === 'response.completed' || output.type === 'response.incomplete' || output.type === 'response.cancelled' || output.type === 'response.failed') return
            }
          }
          finally { socket.removeEventListener('message', onMessage); socket.removeEventListener('close', onClose); signal.removeEventListener('abort', cancel) }
          if (reconnects++ >= 6) throw new TransportError('NETWORK_ERROR', 'Die Verbindung konnte nicht wiederhergestellt werden. Lade den Chat neu, um den gespeicherten Stand abzurufen.')
          await new Promise(resolve => setTimeout(resolve, Math.min(5000, 250 * 2 ** reconnects)))
        }
      }
      finally { streaming.delete(request.generationId) }
    },
  }
}
