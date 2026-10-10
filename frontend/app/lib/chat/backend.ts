import type { ApiSchemas } from '../../types/generated/api'
import type { Conversation } from './conversations'
import type { ChatMessage } from './types'
import { responseError } from './realTransport'

type ServerConversation = ApiSchemas['ConversationResponse']
type ServerMessage = ApiSchemas['MessageResponse']
export interface ChatBootstrap {
  metadata: ServerConversation[]
  activeConversationId: string | null
  path: ApiSchemas['ActivePathResponse'] | null
  drafts: Record<string, string>
}

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
  initialPage: ApiSchemas['ConversationListResponse'] | null = null
  initialPath: ApiSchemas['ActivePathResponse'] | null = null
  onMetadata?: (conversations: ServerConversation[], activeId: string | null) => void
  private pending: Promise<unknown> = Promise.resolve()
  constructor(readonly fetcher: typeof fetch = (...args) => globalThis.fetch(...args)) {}

  async request<T>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
    const response = await this.fetcher(`/api/v1${path}`, {
      method, credentials: 'same-origin', signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15_000)]) : AbortSignal.timeout(15_000), headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
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
    if (value.version < (this.versions.get(value.id) ?? 0)) return
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
  async load(): Promise<ChatBootstrap> {
    await this.pending
    const [list, preferences] = await Promise.all([
      this.request<ApiSchemas['ConversationListResponse']>('/conversations?limit=50'),
      this.request<ApiSchemas['PreferencesResponse']>('/chat/preferences'),
    ])
    this.initialPage = list
    this.preferredModelId = preferences.modelId
    const conversations = [...list.conversations]
    let activeId = preferences.activeConversationId
    this.onMetadata?.(list.conversations, conversations.some(c => c.id === activeId) ? activeId : null)
    if (activeId && !conversations.some(c => c.id === activeId)) {
      try { conversations.push(await this.request<ServerConversation>(`/conversations/${activeId}`)) }
      catch (error) { if ((error as { code?: string }).code === 'NOT_FOUND') activeId = null; else throw error }
    }
    if (conversations.find(c => c.id === activeId)?.archivedAt) activeId = null
    for (const conversation of conversations) this.versions.set(conversation.id, conversation.version)
    if (conversations.length !== list.conversations.length) this.onMetadata?.(conversations, activeId)
    const [drafts, path] = await Promise.all([
      this.request<ApiSchemas['DraftListResponse']>(`/chat/drafts?${new URLSearchParams([['keys', '__new__'], ...(activeId ? [['keys', activeId]] : [])])}`),
      activeId ? this.path(activeId) : Promise.resolve(null),
    ])
    this.initialPath = path
    return {
      metadata: conversations, activeConversationId: activeId, path,
      drafts: { __new__: '', ...(activeId ? { [activeId]: '' } : {}), ...Object.fromEntries(drafts.drafts.map(d => [d.key, d.content])) },
    }
  }
  path(id: string, options: { cursor?: string, beforeMessageId?: string, messageId?: string, preferredLeafId?: string } = {}, signal?: AbortSignal): Promise<ApiSchemas['ActivePathResponse']> {
    return this.request(`/conversations/${id}/active-path?${new URLSearchParams({ limit: '50', ...options })}`, 'GET', undefined, signal)
  }
  page(options: { cursor?: string, q?: string, archiveOnly?: string } = {}, signal?: AbortSignal): Promise<ApiSchemas['ConversationListResponse']> {
    return this.request(`/conversations?${new URLSearchParams({ limit: '50', ...options })}`, 'GET', undefined, signal)
  }
}
