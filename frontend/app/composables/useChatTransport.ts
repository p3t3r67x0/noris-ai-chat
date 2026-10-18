import { createMockTransport } from '../lib/chat/mockTransport'
import { createRealTransport } from '../lib/chat/realTransport'
import type { ChatTransport } from '../lib/chat/types'
import { createWebSocketTransport } from '../lib/chat/webSocketTransport'

export function useChatTransport(): { mode: 'mock' | 'real' | 'websocket', transport: ChatTransport } {
  const mode = useRuntimeConfig().public.chatTransport
  if (mode === 'websocket') {
    const url = useRuntimeConfig().public.chatWebsocketUrl
    const transport = createWebSocketTransport(url ? { url } : {})
    const requestedId = useRoute().query.conversationId
    if (typeof requestedId === 'string') transport.backend!.requestedConversationId = requestedId
    return { mode, transport }
  }
  if (mode !== 'mock' && mode !== 'real') throw new Error('Ungültiger Chat-Transport')
  return { mode, transport: mode === 'real' ? createRealTransport() : createMockTransport() }
}
