import { randomUUID } from 'node:crypto'
import { expect } from '@playwright/test'
import type { APIRequestContext, Page, Route } from '@playwright/test'
import type { ApiSchemas } from '../../app/types/generated/api'
import { clearTestConversations, stableModelCatalog } from './chat-fixtures'

export function loadingGate() {
  let release!: () => void
  const promise = new Promise<void>(resolve => { release = resolve })
  return { promise, release }
}

export async function seedLoadingChats(page: Page, request: APIRequestContext, count = 12) {
  await clearTestConversations(request)
  const ids = [randomUUID(), randomUUID()]
  const messages: ApiSchemas['ImportMessage'][] = []
  const conversations: ApiSchemas['ImportConversation'][] = ids.map((id, chat) => {
    let parent: string | null = null
    const createdAt = '2026-10-01T12:00:00.000Z'
    for (let index = 0; index < count; index++) {
      const messageId = randomUUID()
      const time = new Date(Date.UTC(2026, 9, 1, 12, index)).toISOString()
      messages.push({ id: messageId, conversationId: id, parentMessageId: parent,
        role: index % 2 ? 'assistant' : 'user', status: 'completed',
        content: `Synthetischer Verlauf ${chat ? 'B' : 'A'}, Beitrag ${index}.\n\n${'Ein neutraler Absatz prüft die gespeicherte Leseposition. '.repeat(3)}`,
        modelId: index % 2 ? 'fixture-alpha' : null, createdAt: time, updatedAt: time })
      parent = messageId
    }
    return { id, title: `Ladetest ${chat ? 'B' : 'A'}`, titleSource: 'manual', activeLeafMessageId: parent, createdAt, updatedAt: messages.at(-1)!.updatedAt }
  })
  const imported = await request.post('/api/v1/conversations/import', { data: {
    conversations, messages, activeConversationId: ids[0], drafts: { [ids[0]!]: 'Gespeicherter Entwurf A', [ids[1]!]: 'Gespeicherter Entwurf B' },
  } })
  expect(imported.ok()).toBe(true)
  expect((await imported.json()).conflicts).toEqual([])
  expect((await request.put('/api/v1/chat/preferences', { data: { activeConversationId: ids[0], modelId: 'fixture-alpha' } })).ok()).toBe(true)
  await stableModelCatalog(page)
  return { first: ids[0]!, second: ids[1]!, messages }
}

export async function holdLoadingPath(page: Page, id: string) {
  let gate = loadingGate()
  let hit = loadingGate()
  let fail = false
  let requests = 0
  const handler = async (route: Route) => {
    requests++
    const current = gate
    hit.release()
    await current.promise
    if (fail) {
      fail = false
      await route.fulfill({ status: 503, json: { error: { code: 'INTERNAL_ERROR', message: 'Synthetic loading failure' } } })
    }
    else await route.continue()
  }
  await page.route(`**/api/v1/conversations/${id}/active-path?*`, handler)
  return {
    get requests() { return requests },
    get hit() { return hit.promise },
    release() { gate.release() },
    fail() { fail = true; gate.release() },
    reset() { gate = loadingGate(); hit = loadingGate() },
  }
}
