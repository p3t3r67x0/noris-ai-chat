import { createMockTransport } from '../lib/chat/mockTransport'
import { createRealTransport } from '../lib/chat/realTransport'
import type { ChatTransport } from '../lib/chat/types'

export function useChatTransport(): { mode: 'mock' | 'real', transport: ChatTransport } {
  const mode = useRuntimeConfig().public.chatTransport
  if (mode !== 'mock' && mode !== 'real') throw new Error('Ungültiger Chat-Transport')
  return { mode, transport: mode === 'real' ? createRealTransport() : createMockTransport() }
}
