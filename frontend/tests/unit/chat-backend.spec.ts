import { describe, expect, it, vi } from 'vitest'
import { ChatBackend } from '../../app/lib/chat/backend'
import type { ApiSchemas } from '../../app/types/generated/api'

const conversation: ApiSchemas['ConversationResponse'] = {
  id: '00000000-0000-4000-8000-000000000001', title: 'Automatischer Titel', titleSource: 'generated', version: 3,
  activeLeafMessageId: null, createdAt: '2026-10-10T00:00:00Z', updatedAt: '2026-10-10T00:00:00Z', archivedAt: null, lastMessageAt: null,
}
const conflict = () => Response.json({ error: { code: 'VERSION_CONFLICT', message: 'Der Chat wurde geändert.' } }, { status: 409 })

describe('chat metadata version conflicts', () => {
  it('keeps the started revision when recovery and normal lists overlap during the first send', async () => {
    const started = { ...conversation, sidebarVisible: true, lifecycle: 'GENERATING', version: 2 }
    const prepared = { ...conversation, sidebarVisible: false, lifecycle: 'EMPTY', version: 1 }
    const fetcher = vi.fn<typeof fetch>(async (input) => {
      const path = String(input)
      if (path.includes('/chat/preferences')) return Response.json({ activeConversationId: null, modelId: null })
      if (path.includes('/chat/drafts')) return Response.json({ drafts: [] })
      return Response.json({ conversations: path.includes('preparedOnly=true') ? [prepared] : [started] })
    })
    const backend = new ChatBackend(fetcher)
    const metadata = vi.fn(); backend.onMetadata = metadata
    const result = await backend.load()
    expect(result.metadata).toEqual([started])
    expect(metadata).toHaveBeenCalledWith([started], null)
    expect(backend.versions.get(conversation.id)).toBe(2)
  })
  it('does not lower the known version when an initial load finishes after a live update', async () => {
    let release!: (value: Response) => void
    const preferences = new Promise<Response>(resolve => { release = resolve })
    const fallback = { ...conversation, title: 'Neuer Chat', titleSource: 'fallback' as const, version: 1 }
    const manual = { ...conversation, title: 'Mein manueller Titel', titleSource: 'manual' as const, version: 4 }
    const fetcher = vi.fn<typeof fetch>(async (input) => {
      const path = String(input)
      if (path.includes('/chat/preferences')) return preferences
      if (path.includes('/chat/drafts')) return Response.json({ drafts: [] })
      return Response.json({ conversations: [fallback] })
    })
    const backend = new ChatBackend(fetcher)
    const update = vi.fn(); backend.onConversation = update
    const loading = backend.load()
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(4))
    backend.remember(manual)
    release(Response.json({ activeConversationId: null, modelId: null }))
    await loading
    backend.remember(conversation)
    expect(backend.versions.get(conversation.id)).toBe(4)
    expect(update).toHaveBeenCalledExactlyOnceWith(manual)
  })

  it('does not lower the known version when creation returns after a live update', async () => {
    let release!: (value: Response) => void
    const fetcher = vi.fn<typeof fetch>(() => new Promise(resolve => { release = resolve }))
    const backend = new ChatBackend(fetcher)
    const creating = backend.ensure({ ...conversation, titleGenerationAttempted: true })
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledOnce())
    backend.remember(conversation)
    release(Response.json({ ...conversation, version: 1 }))
    expect(await creating).toBe(3)
    expect(backend.versions.get(conversation.id)).toBe(3)
  })

  it('reapplies only the explicit mode after a generation changes the version', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(conflict())
      .mockResolvedValueOnce(Response.json({ ...conversation, activeLeafMessageId: 'answer' }))
      .mockResolvedValueOnce(Response.json({ ...conversation, activeLeafMessageId: 'answer', conversationMode: 'learning', version: 4 }))
    const backend = new ChatBackend(fetcher)
    backend.versions.set(conversation.id, 2)
    await backend.patch(conversation.id, { conversationMode: 'learning' })
    expect(JSON.parse(String(fetcher.mock.calls[2]?.[1]?.body))).toEqual({ conversationMode: 'learning', version: 3 })
    expect(backend.versions.get(conversation.id)).toBe(4)
  })
  it.each(['generated', 'fallback'] as const)('reapplies a manual title once after a %s title changed the version', async (titleSource) => {
    const fetcher = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(conflict())
      .mockResolvedValueOnce(Response.json({ ...conversation, titleSource }))
      .mockResolvedValueOnce(Response.json({ ...conversation, title: 'Mein manueller Titel', titleSource: 'manual', version: 4 }))
    const backend = new ChatBackend(fetcher)
    backend.versions.set(conversation.id, 2)
    const remember = vi.fn(); backend.onConversation = remember

    await backend.patch(conversation.id, { title: 'Mein manueller Titel' })

    expect(fetcher).toHaveBeenCalledTimes(3)
    expect(fetcher.mock.calls.map(([, options]) => options?.method)).toEqual(['PATCH', 'GET', 'PATCH'])
    expect(JSON.parse(String(fetcher.mock.calls[0]?.[1]?.body))).toEqual({ title: 'Mein manueller Titel', version: 2 })
    expect(JSON.parse(String(fetcher.mock.calls[2]?.[1]?.body))).toEqual({ title: 'Mein manueller Titel', version: 3 })
    expect(backend.versions.get(conversation.id)).toBe(4)
    expect(remember).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ titleSource: 'manual', title: 'Mein manueller Titel' }))
  })

  it('preserves a competing manual title instead of overwriting it', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(conflict()).mockResolvedValueOnce(Response.json({ ...conversation, titleSource: 'manual' }))
    const backend = new ChatBackend(fetcher)
    backend.versions.set(conversation.id, 2)
    await expect(backend.patch(conversation.id, { title: 'Anderer manueller Titel' })).rejects.toMatchObject({ code: 'VERSION_CONFLICT' })
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('stops after a second conflict', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(conflict()).mockResolvedValueOnce(Response.json(conversation)).mockResolvedValueOnce(conflict())
    const backend = new ChatBackend(fetcher)
    backend.versions.set(conversation.id, 2)
    await expect(backend.patch(conversation.id, { title: 'Mein Titel' })).rejects.toMatchObject({ code: 'VERSION_CONFLICT' })
    expect(fetcher).toHaveBeenCalledTimes(3)
  })

  it.each([{ archived: true }, { activeLeafMessageId: conversation.id }, { title: 'Titel', archived: false }])('does not replay other conflicting changes: %j', async (change) => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(conflict())
    const backend = new ChatBackend(fetcher)
    await expect(backend.patch(conversation.id, change)).rejects.toMatchObject({ code: 'VERSION_CONFLICT' })
    expect(fetcher).toHaveBeenCalledOnce()
  })

  it('does not replay authentication errors', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(Response.json({ error: { code: 'ACCESS_DENIED', message: 'Anmeldung erforderlich.' } }, { status: 401 }))
    const backend = new ChatBackend(fetcher)
    await expect(backend.patch(conversation.id, { title: 'Mein Titel' })).rejects.toMatchObject({ code: 'ACCESS_DENIED' })
    expect(fetcher).toHaveBeenCalledOnce()
  })
})

describe('direct conversation bootstrap', () => {
  it('uses one requested path instead of the preferred path, then releases the URL intent', async () => {
    const other = { ...conversation, id: '00000000-0000-4000-8000-0000000000ab', title: 'Direkter synthetischer Chat' }
    const fetcher = vi.fn<typeof fetch>(async input => {
      const path = String(input)
      if (path.includes('/chat/preferences')) return Response.json({ activeConversationId: conversation.id, modelId: null })
      if (path.includes('/chat/drafts')) return Response.json({ drafts: [] })
      if (path.includes('/active-path')) return Response.json({ conversation: path.includes(other.id) ? other : conversation, messages: [], variants: [], hasMore: false, nextCursor: null, boundaryParentId: null, leafMessageId: null })
      return Response.json({ conversations: path.includes('pinned=true') || path.includes('preparedOnly=true') ? [] : [conversation, other] })
    })
    const backend = new ChatBackend(fetcher)
    backend.requestedConversationId = other.id.toUpperCase()
    expect((await backend.load()).activeConversationId).toBe(other.id)
    const paths = fetcher.mock.calls.map(([input]) => String(input)).filter(path => path.includes('/active-path'))
    expect(paths).toHaveLength(1)
    expect(paths[0]).toContain(other.id)
    expect(backend.requestedConversationId).toBeUndefined()
    expect((await backend.load()).activeConversationId).toBe(conversation.id)
  })

  it('rejects malformed URL identifiers before issuing a request', async () => {
    const fetcher = vi.fn<typeof fetch>()
    const backend = new ChatBackend(fetcher)
    backend.requestedConversationId = '../chat/preferences'
    await expect(backend.load()).rejects.toMatchObject({ code: 'NOT_FOUND' })
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('opens an explicitly new chat without loading the preferred conversation', async () => {
    const fetcher = vi.fn<typeof fetch>(async input => {
      const path = String(input)
      if (path.includes('/chat/preferences')) return Response.json({ activeConversationId: conversation.id, modelId: null })
      if (path.includes('/chat/drafts')) return Response.json({ drafts: [] })
      if (path.includes('/active-path')) return Response.json({ conversation, messages: [], variants: [], hasMore: false, nextCursor: null, boundaryParentId: null, leafMessageId: null })
      return Response.json({ conversations: path.includes('pinned=true') || path.includes('preparedOnly=true') ? [] : [conversation] })
    })
    const backend = new ChatBackend(fetcher)
    backend.requestedConversationId = null
    expect(await backend.load()).toMatchObject({ activeConversationId: null, path: null })
    expect(fetcher.mock.calls.some(([input]) => String(input).includes('/active-path'))).toBe(false)
    expect((await backend.load()).activeConversationId).toBe(conversation.id)
  })

  it('preserves an unavailable direct target for retry without falling back to another conversation', async () => {
    const fetcher = vi.fn<typeof fetch>(async input => {
      const path = String(input)
      if (path.includes('/chat/preferences')) return Response.json({ activeConversationId: conversation.id, modelId: null })
      if (path.includes('/conversations/')) return Response.json({ error: { code: 'NOT_FOUND', message: 'Chat nicht gefunden.' } }, { status: 404 })
      return Response.json({ conversations: [conversation] })
    })
    const backend = new ChatBackend(fetcher)
    const target = '00000000-0000-4000-8000-000000000099'
    backend.requestedConversationId = target
    await expect(backend.load()).rejects.toMatchObject({ code: 'NOT_FOUND' })
    expect(backend.requestedConversationId).toBe(target)
    expect(fetcher.mock.calls.some(([input]) => String(input).includes('/active-path'))).toBe(false)
  })
})
