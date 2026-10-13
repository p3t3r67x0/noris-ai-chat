import type { ApiSchemas } from '../../types/generated/api'
import type { Conversation, ConversationMode } from './conversations'
import type { ChatMessage } from './types'
import { responseError, TransportError } from './realTransport'
import type { ReasoningPreference } from './reasoning'

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
    ...(value.attachments?.length ? { attachments: value.attachments } : {}),
  }
}

/** Resource client only. The existing useChat state owns every rendered record. */
export class ChatBackend {
  versions = new Map<string, number>()
  preferredModelId: string | null = null
  onConversation?: (conversation: ServerConversation) => void
  onPinnedPage?: (page: ApiSchemas['ConversationListResponse']) => void
  onDeleted?: (id: string) => void
  private deleted = new Set<string>()
  onMessage?: (message: ServerMessage) => void
  initialPage: ApiSchemas['ConversationListResponse'] | null = null
  initialPinnedPage: ApiSchemas['ConversationListResponse'] | null = null
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
    if (this.deleted.has(value.id)) return
    if (value.version < (this.versions.get(value.id) ?? 0)) return
    this.versions.set(value.id, value.version)
    this.onConversation?.(value)
  }
  forget(id: string, version = this.versions.get(id) ?? 1): void {
    if (version < (this.versions.get(id) ?? 0)) return
    this.deleted.add(id)
    this.versions.delete(id)
    this.onDeleted?.(id)
    // Bound tombstones along with the existing metadata cache.
    if (this.deleted.size > 600) this.deleted.delete(this.deleted.values().next().value!)
  }
  isDeleted(id: string): boolean { return this.deleted.has(id) }
  async refreshMetadata(): Promise<void> {
    // Recover updates missed while disconnected, including an older active chat.
    // Keep messages and unsent drafts under the existing useChat state.
    const [page, pins] = await Promise.all([this.page({ pinned: 'false' }), this.page({ pinned: 'true' })])
    for (const value of [...page.conversations, ...pins.conversations]) this.remember(value)
    this.onPinnedPage?.(pins)
    const present = new Set([...page.conversations, ...pins.conversations].map(value => value.id))
    const missing = [...this.versions.keys()].filter(id => !present.has(id))
    for (let offset = 0; offset < missing.length; offset += 10) {
      await Promise.all(missing.slice(offset, offset + 10).map(async id => {
        try { this.remember(await this.request<ServerConversation>(`/conversations/${id}`)) }
        catch (error) { if (!(error instanceof TransportError) || error.code !== 'NOT_FOUND') throw error; this.forget(id) }
      }))
    }
  }
  ensure(conversation: Conversation): Promise<number> {
    return this.enqueue(async () => {
      if (!this.versions.has(conversation.id)) {
        const value = await this.request<ServerConversation>('/conversations', 'POST', { id: conversation.id, title: conversation.title, prepared: conversation.sidebarVisible === false, conversationMode: conversation.conversationMode ?? 'normal', reasoningPreference: conversation.reasoningPreference ?? null })
        this.versions.set(value.id, Math.max(value.version, this.versions.get(value.id) ?? 0))
      }
      return this.versions.get(conversation.id)!
    })
  }
  patch(id: string, change: { title?: string, archived?: boolean, pinned?: boolean, activeLeafMessageId?: string, conversationMode?: ConversationMode, reasoningPreference?: ReasoningPreference | null }): Promise<void> {
    return this.enqueue(async () => {
      const path = `/conversations/${id}`
      const version = this.versions.get(id)
      let value: ServerConversation
      try { value = await this.request<ServerConversation>(path, 'PATCH', { ...change, version }) }
      catch (error) {
        if (error instanceof TransportError && error.code === 'VERSION_CONFLICT' && (change.conversationMode !== undefined || Object.hasOwn(change, 'reasoningPreference'))) {
          const current = await this.request<ServerConversation>(path)
          this.remember(current)
          value = await this.request<ServerConversation>(path, 'PATCH', { ...change, version: current.version })
          this.remember(value)
          return
        }
        if (!(error instanceof TransportError) || error.code !== 'VERSION_CONFLICT' || typeof change.title !== 'string' || change.archived !== undefined || change.activeLeafMessageId !== undefined) throw error
        // A generated title can commit before its WebSocket update reaches us.
        // Reapply only the explicit title, once; competing manual edits still win.
        const current = await this.request<ServerConversation>(path)
        if (current.titleSource === 'manual' || version === undefined || current.version <= version) throw error
        value = await this.request<ServerConversation>(path, 'PATCH', { ...change, version: current.version })
      }
      this.remember(value)
    })
  }
  remove(id: string): Promise<void> {
    return this.enqueue(async () => { await this.request(`/conversations/${id}`, 'DELETE'); this.forget(id) })
  }
  draft(key: string, content: string): Promise<void> {
    return this.enqueue(() => this.request(key === '__new__' ? '/chat/drafts/new' : `/conversations/${key}/draft`, 'PUT', { content }))
  }
  preferences(activeConversationId: string | null, modelId?: string): Promise<void> {
    return this.enqueue(() => this.request('/chat/preferences', 'PUT', { activeConversationId, ...(modelId ? { modelId } : {}) }))
  }
  async load(): Promise<ChatBootstrap> {
    await this.pending
    const [list, pins, prepared, preferences] = await Promise.all([
      this.page({ pinned: 'false' }),
      this.page({ pinned: 'true' }),
      // Recover upload/settings drafts through the existing metadata state.
      // This explicit recovery page never feeds a conversation picker.
      this.page({ preparedOnly: 'true' }),
      this.request<ApiSchemas['PreferencesResponse']>('/chat/preferences'),
    ])
    this.initialPage = list
    this.initialPinnedPage = pins
    this.preferredModelId = preferences.modelId
    const metadata = new Map<string, ServerConversation>()
    for (const value of [...list.conversations, ...pins.conversations, ...prepared.conversations]) {
      // The first send can commit between the parallel list/recovery reads.
      if (value.version >= (metadata.get(value.id)?.version ?? 0)) metadata.set(value.id, value)
    }
    const conversations = [...metadata.values()]
    let activeId = preferences.activeConversationId
    this.onMetadata?.([...conversations], conversations.some(c => c.id === activeId) ? activeId : null)
    if (activeId && !conversations.some(c => c.id === activeId)) {
      try { conversations.push(await this.request<ServerConversation>(`/conversations/${activeId}`)) }
      catch (error) { if ((error as { code?: string }).code === 'NOT_FOUND') activeId = null; else throw error }
    }
    if (conversations.find(c => c.id === activeId)?.archivedAt) activeId = null
    for (const conversation of conversations) this.versions.set(conversation.id, Math.max(conversation.version, this.versions.get(conversation.id) ?? 0))
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
  page(options: { cursor?: string, q?: string, archiveOnly?: string, pinned?: string, preparedOnly?: string } = {}, signal?: AbortSignal): Promise<ApiSchemas['ConversationListResponse']> {
    return this.request(`/conversations?${new URLSearchParams({ limit: '50', ...options })}`, 'GET', undefined, signal)
  }
}
