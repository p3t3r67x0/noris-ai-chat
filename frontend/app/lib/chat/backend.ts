import type { ApiSchemas } from '../../types/generated/api'
import type { Conversation } from './conversations'
import type { ChatMessage } from './types'
import type { ChatSnapshot } from './persistence'
import { responseError } from './realTransport'

type ServerConversation = ApiSchemas['ConversationResponse']
type ServerMessage = ApiSchemas['MessageResponse']

export function conversationFromServer(value: ServerConversation): Conversation {
  return { ...value, titleGenerationAttempted: value.titleSource !== 'fallback' }
}
export function messageFromServer(value: ServerMessage): ChatMessage {
  return {
    id: value.id, conversationId: value.conversationId, parentMessageId: value.parentMessageId,
    role: value.role, content: value.content, createdAt: new Date(value.createdAt).toISOString(),
    status: value.status === 'pending' ? 'submitting' : value.status,
    continuationCount: value.continuationCount ?? 0,
    ...(value.errorCode ? { errorCode: value.errorCode } : {}),
    ...(value.errorMessage ? { errorMessage: value.errorMessage } : {}),
    ...(value.generationId ? { generationId: value.generationId } : {}),
    ...(value.modelId ? { modelId: value.modelId } : {}),
    ...(value.editedFromMessageId ? { editedFromMessageId: value.editedFromMessageId } : {}),
  }
}

/** Resource client only. The existing useChat state owns every rendered record. */
export class ChatBackend {
  versions = new Map<string, number>()
  preferredModelId: string | null = null
  onConversation?: (conversation: ServerConversation) => void
  private pending: Promise<unknown> = Promise.resolve()
  constructor(readonly fetcher: typeof fetch = (...args) => globalThis.fetch(...args)) {}

  async request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const response = await this.fetcher(`/api/v1${path}`, {
      method, credentials: 'same-origin', signal: AbortSignal.timeout(15_000), headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
    if (!response.ok) throw await responseError(response)
    return (response.status === 204 ? undefined : await response.json()) as T
  }
  private enqueue<T>(operation: () => Promise<T>): Promise<T> {
    const result = this.pending.then(operation)
    this.pending = result.catch(() => {})
    return result
  }
  remember(value: ServerConversation): void {
    this.versions.set(value.id, value.version)
    this.onConversation?.(value)
  }
  ensure(conversation: Conversation): Promise<number> {
    return this.enqueue(async () => {
      if (!this.versions.has(conversation.id)) {
        const value = await this.request<ServerConversation>('/conversations', 'POST', { id: conversation.id, title: conversation.title })
        this.versions.set(value.id, value.version)
      }
      return this.versions.get(conversation.id)!
    })
  }
  patch(id: string, change: { title?: string, archived?: boolean, activeLeafMessageId?: string }): Promise<void> {
    return this.enqueue(async () => {
      const value = await this.request<ServerConversation>(`/conversations/${id}`, 'PATCH', { ...change, version: this.versions.get(id) })
      this.remember(value)
    })
  }
  remove(id: string): Promise<void> {
    return this.enqueue(async () => { await this.request(`/conversations/${id}`, 'DELETE'); this.versions.delete(id) })
  }
  draft(key: string, content: string): Promise<void> {
    return this.enqueue(() => this.request(key === '__new__' ? '/chat/drafts/new' : `/conversations/${key}/draft`, 'PUT', { content }))
  }
  preferences(activeConversationId: string | null, modelId?: string): Promise<void> {
    return this.enqueue(() => this.request('/chat/preferences', 'PUT', { activeConversationId, ...(modelId ? { modelId } : {}) }))
  }
  async load(): Promise<ChatSnapshot> {
    await this.pending
    const [list, drafts, preferences] = await Promise.all([
      this.request<ApiSchemas['ConversationListResponse']>('/conversations?archived=true'),
      this.request<ApiSchemas['DraftListResponse']>('/chat/drafts'),
      this.request<ApiSchemas['PreferencesResponse']>('/chat/preferences'),
    ])
    this.preferredModelId = preferences.modelId
    const records = await Promise.all(list.conversations.map(async (c) => {
      this.versions.set(c.id, c.version)
      return this.request<ApiSchemas['MessageListResponse']>(`/conversations/${c.id}/messages`)
    }))
    return {
      version: 1, conversations: { version: 1, conversations: Object.fromEntries(list.conversations.map(c => [c.id, conversationFromServer(c)])), activeConversationId: preferences.activeConversationId },
      messages: Object.fromEntries(records.flatMap(r => r.messages.map(m => [m.id, messageFromServer(m)]))),
      drafts: Object.fromEntries(drafts.drafts.map(d => [d.key, d.content])), preferredLeaves: {},
    }
  }
}
