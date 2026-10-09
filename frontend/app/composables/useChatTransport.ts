import { createMockTransport } from '../lib/chat/mockTransport'
import { createRealTransport } from '../lib/chat/realTransport'
import type { ChatTransport } from '../lib/chat/types'
import { createWebSocketTransport } from '../lib/chat/webSocketTransport'

export function useChatTransport(): { mode: 'mock' | 'real' | 'websocket', transport: ChatTransport } {
  const mode = useRuntimeConfig().public.chatTransport
  if (mode === 'websocket') {
    const url = useRuntimeConfig().public.chatWebsocketUrl
    return { mode, transport: createWebSocketTransport(url ? { url } : {}) }
  }
  if (mode !== 'mock' && mode !== 'real') throw new Error('Ungültiger Chat-Transport')
  return { mode, transport: mode === 'real' ? createRealTransport() : createMockTransport() }
}
