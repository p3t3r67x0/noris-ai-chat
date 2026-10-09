import type { ChatModelId } from '../../composables/useModelSelection'

export type GenerationStatus = 'idle' | 'submitting' | 'streaming' | 'completed' | 'cancelled' | 'failed'
export type MessageStatus = Exclude<GenerationStatus, 'idle'>
export interface ChatMessage {
  id: string
  conversationId: string
  parentMessageId: string | null
  role: 'user' | 'assistant'
  content: string
  status: MessageStatus
  createdAt: string
}
export type MessageRecords = Record<string, ChatMessage>
export interface ChatRequest {
  generationId: string
  conversationId: string
  inputMessageId: string
  modelId: ChatModelId
  messages: readonly Pick<ChatMessage, 'role' | 'content'>[]
  attempt: number
}
export type StreamEvent = { seq: number } & (
  | { type: 'response.started' }
  | { type: 'response.output_text.delta', delta: string }
  | { type: 'response.completed' }
  | { type: 'response.cancelled' }
  | { type: 'response.failed', code: string, message: string }
)
export interface ChatTransport {
  stream: (request: ChatRequest, signal: AbortSignal) => AsyncIterable<StreamEvent>
}
export const MAX_MESSAGE_LENGTH = 32_000
export const isBusy = (status: GenerationStatus): boolean => status === 'submitting' || status === 'streaming'

export function visiblePath(records: MessageRecords, conversationId: string, leafId: string | null): ChatMessage[] {
  const path: ChatMessage[] = []
  const seen = new Set<string>()
  let current = leafId
  while (current !== null) {
    const message: ChatMessage | undefined = Object.hasOwn(records, current) ? records[current] : undefined
    if (!message || message.conversationId !== conversationId || seen.has(current)) throw new Error('Ungültiger Gesprächspfad')
    seen.add(current)
    path.unshift(message)
    current = message.parentMessageId
  }
  return path
}
