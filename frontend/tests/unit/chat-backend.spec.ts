import { describe, expect, it, vi } from 'vitest'
import { ChatBackend } from '../../app/lib/chat/backend'
import type { ApiSchemas } from '../../app/types/generated/api'

const conversation: ApiSchemas['ConversationResponse'] = {
  id: '00000000-0000-4000-8000-000000000001', title: 'Automatischer Titel', titleSource: 'generated', version: 3,
  activeLeafMessageId: null, createdAt: '2026-10-10T00:00:00Z', updatedAt: '2026-10-10T00:00:00Z', archivedAt: null, lastMessageAt: null,
}
const conflict = () => Response.json({ error: { code: 'VERSION_CONFLICT', message: 'Der Chat wurde geändert.' } }, { status: 409 })

describe('chat metadata version conflicts', () => {
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
