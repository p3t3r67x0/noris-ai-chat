import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { chatActions } from '../e2e/sidebar-helpers'
import type { ApiSchemas } from '../../app/types/generated/api'
import { randomUUID } from 'node:crypto'

const namespace = randomUUID().slice(0, 24)
const id = (n: number) => `${namespace}${String(n).padStart(12, '0')}`
async function clear(request: APIRequestContext) {
  let cursor: string | null = null
  do {
    const result = await request.get('/api/v1/conversations', { params: { archived: 'true', limit: 100, ...(cursor ? { cursor } : {}) } })
    expect(result.ok()).toBe(true)
    const data: ApiSchemas['ConversationListResponse'] = await result.json()
    for (const c of data.conversations) await request.delete(`/api/v1/conversations/${c.id}`)
    cursor = data.nextCursor ?? null
  } while (cursor)
}
async function open(page: Page) {
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  await expect(page.getByRole('navigation', { name: 'Gespräche', exact: true })).toBeVisible()
}
async function seed(request: APIRequestContext) {
  const conversations = Array.from({ length: 65 }, (_, i) => ({ id: id(i + 1), title: i === 0 ? 'Sehr alter fixierter Chat' : `Synthetic ${i}`, titleSource: 'manual', createdAt: '2020-01-01T00:00:00Z', updatedAt: new Date(Date.UTC(2020, 0, 1 + i)).toISOString(), archivedAt: null, activeLeafMessageId: null }))
  const messages = conversations.map((conversation, i) => ({ id: id(1000 + i), conversationId: conversation.id, role: 'user', content: 'Synthetic persisted input', status: 'completed', createdAt: conversation.createdAt, updatedAt: conversation.updatedAt }))
  const result = await request.post('/api/v1/conversations/import', { data: { conversations, messages, drafts: {}, activeConversationId: id(65) } })
  expect(result.ok()).toBe(true)
  expect((await request.put('/api/v1/chat/preferences', { data: { activeConversationId: id(65), modelId: 'fixture-alpha' } })).ok()).toBe(true)
  expect((await request.patch(`/api/v1/conversations/${id(1)}`, { data: { pinned: true, version: 1 } })).ok()).toBe(true)
}
test.beforeEach(async ({ request }) => { await clear(request); await seed(request) })
test.afterEach(async ({ request }) => { await clear(request) })

test('old pins survive pagination and reload; two tabs synchronize pin, unpin, archive and delete', async ({ page, context, request }) => {
  test.setTimeout(60_000)
  const second = await context.newPage()
  await page.goto('/'); await second.goto('/')
  await open(page); await open(second)
  const active = page.locator(`[data-conversation-id="${id(65)}"]:visible`)
  await expect(active).toHaveAttribute('data-active', 'true')
  const pinned = (p: Page) => p.getByRole('region', { name: 'Fixierte Chats', exact: true })
  await expect(pinned(page)).toContainText('Sehr alter fixierter Chat')
  await expect(pinned(second)).toContainText('Sehr alter fixierter Chat')
  await expect(page.locator('.conversation-row:visible')).toHaveCount(51)
  await page.getByRole('button', { name: 'Weitere Chats laden', exact: true }).click()
  await expect(page.locator('.conversation-row:visible')).toHaveCount(65)
  await expect(page.locator(`[data-conversation-id="${id(1)}"]:visible`)).toHaveCount(1)
  const oldRow = page.locator(`[data-conversation-id="${id(1)}"]:visible`)
  await oldRow.hover()
  await oldRow.getByRole('button', { name: 'Chat-Fixierung lösen', exact: true }).click()
  await expect(pinned(page)).toHaveCount(0)
  await expect(pinned(second)).toHaveCount(0)
  await oldRow.hover()
  await chatActions(page, 'Sehr alter fixierter Chat').click()
  await page.getByRole('menuitem', { name: 'Chat anpinnen', exact: true }).click()
  await expect(pinned(second)).toContainText('Sehr alter fixierter Chat')
  await page.reload(); await open(page)
  await expect(pinned(page)).toContainText('Sehr alter fixierter Chat')
  // The mobile drawer makes the composer inert; verify the active chat itself.
  await expect(active).toHaveAttribute('data-active', 'true')
  const authority = await (await request.get(`/api/v1/conversations/${id(1)}`)).json()
  expect((await request.patch(`/api/v1/conversations/${id(1)}`, { data: { archived: true, version: authority.version } })).ok()).toBe(true)
  await expect(pinned(page)).toHaveCount(0)
  await expect(pinned(second)).toHaveCount(0)
  expect((await request.patch(`/api/v1/conversations/${id(1)}`, { data: { archived: false, version: authority.version + 1 } })).ok()).toBe(true)
  await expect(pinned(page)).toContainText('Sehr alter fixierter Chat')
  expect((await request.delete(`/api/v1/conversations/${id(1)}`)).ok()).toBe(true)
  await expect(page.locator(`[data-conversation-id="${id(1)}"]`)).toHaveCount(0)
  await expect(second.locator(`[data-conversation-id="${id(1)}"]`)).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await second.close()
})
