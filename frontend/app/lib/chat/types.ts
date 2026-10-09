import type { ChatModelId } from '../../composables/useModelSelection'
import type { ApiPaths } from '../../types/generated/api'

export type ConversationTitleRequest = ApiPaths['/api/v1/llm/conversation-title']['post']['requestBody']
export type ConversationTitleResponse = ApiPaths['/api/v1/llm/conversation-title']['post']['responses'][200]

export type GenerationStatus = 'idle' | 'submitting' | 'streaming' | 'completed' | 'incomplete' | 'cancelled' | 'failed'
export type MessageStatus = Exclude<GenerationStatus, 'idle'>
export interface ChatMessage {
  id: string
  conversationId: string
  parentMessageId: string | null
  role: 'user' | 'assistant'
  content: string
  status: MessageStatus
  createdAt: string
  editedFromMessageId?: string
  modelId?: string
  continuationCount?: number
  errorCode?: string
  errorMessage?: string
}
export type MessageRecords = Record<string, ChatMessage>
export interface ChatRequest {
  generationId: string
  conversationId: string
  inputMessageId: string
  modelId: ChatModelId
  messages: readonly Pick<ChatMessage, 'role' | 'content'>[]
  attempt: number
  operation?: 'generate' | 'continue'
  assistantMessageId?: string
  continuationCount?: number
}
export type StreamEvent = { seq: number } & (
  | { type: 'response.started' }
  | { type: 'response.output_text.delta', delta: string }
  | { type: 'response.completed' }
  | { type: 'response.incomplete', reason: 'output_limit' }
  | { type: 'response.cancelled' }
  | { type: 'response.failed', code: string, message: string }
)
export interface ChatTransport {
  stream: (request: ChatRequest, signal: AbortSignal) => AsyncIterable<StreamEvent>
  generateTitle?: (request: ConversationTitleRequest, signal: AbortSignal) => Promise<ConversationTitleResponse>
}
export const NEW_CHAT_DRAFT = '__new__'
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
