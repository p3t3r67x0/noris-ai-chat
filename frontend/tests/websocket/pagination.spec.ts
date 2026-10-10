import { expect, test } from '@playwright/test'
import type { ApiSchemas } from '../../app/types/generated/api'
import type { APIRequestContext } from '@playwright/test'

async function clearChats(request: APIRequestContext): Promise<void> {
  let cursor: string | null = null
  do {
    const response = await request.get('/api/v1/conversations', { params: { archived: true, limit: 100, ...(cursor ? { cursor } : {}) } })
    expect(response.ok()).toBe(true)
    const data: ApiSchemas['ConversationListResponse'] = await response.json()
    for (const row of data.conversations) expect((await request.delete(`/api/v1/conversations/${row.id}`)).ok()).toBe(true)
    cursor = data.nextCursor ?? null
  } while (cursor)
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null, modelId: null } })
}
let prefix = globalThis.crypto.randomUUID().slice(0, 8)
const uuid = (offset: number) => `${prefix}-0000-4000-8000-${String(offset).padStart(12, '0')}`
async function seed(request: APIRequestContext) {
  prefix = globalThis.crypto.randomUUID().slice(0, 8)
  const conversationId = uuid(900)
  const messages = Array.from({ length: 1002 }, (_, index) => ({
    id: uuid(10000 + index), conversationId, parentMessageId: index ? uuid(9999 + index) : null,
    role: index % 2 ? 'assistant' : 'user', content: `Synthetic node ${index}`, status: 'completed', modelId: 'fixture-alpha',
    createdAt: new Date(Date.UTC(2020, 0, 1, 0, 0, index)).toISOString(), updatedAt: new Date(Date.UTC(2020, 0, 1, 0, 0, index)).toISOString(),
  }))
  messages.push({ ...messages[999]!, id: uuid(20000), content: 'Alternative outside loaded branch', createdAt: '2020-02-01T00:00:00.000Z', updatedAt: '2020-02-01T00:00:00.000Z' })
  const conversations: ApiSchemas['ImportConversation'][] = Array.from({ length: 120 }, (_, index) => ({ id: uuid(index + 1), title: `Sidebar chat ${index + 1}`, titleSource: 'manual', createdAt: '2026-01-01T00:00:00.000Z', updatedAt: new Date(Date.UTC(2026, 0, 1, 0, 0, index)).toISOString(), activeLeafMessageId: null, archivedAt: null }))
  conversations.push({ ...conversations[0]!, id: conversationId, title: 'Old active long chat', updatedAt: '2020-01-01T00:00:00.000Z', activeLeafMessageId: uuid(11001) })
  const result = await request.post('/api/v1/conversations/import', { data: { conversations, messages, drafts: { [conversationId]: 'Persisted long-chat draft' }, activeConversationId: conversationId } })
  expect(result.ok()).toBe(true)
  expect((await result.json()).conflicts).toEqual([])
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: conversationId, modelId: 'fixture-alpha' } })
  return conversationId
}

test.beforeEach(async ({ request }) => { await clearChats(request) })
test.afterEach(async ({ request }) => { await clearChats(request) })

test('loads only metadata and active window, pages history, resolves unseen variants and searches all chats', async ({ page, request }) => {
  test.setTimeout(120000)
  const conversationId = await seed(request)
  const calls: string[] = []
  page.on('request', event => { if (event.url().includes('/api/v1/conversations')) calls.push(event.url()) })
  await page.goto('/')
  await expect(page.locator('.chat-timeline')).toContainText('Synthetic node 1001')
  await expect(page.getByRole('textbox', { name: 'Nachricht' })).toHaveValue('Persisted long-chat draft')
  expect(calls.filter(url => url.includes('/active-path'))).toHaveLength(1)
  expect(calls.filter(url => url.includes('/messages'))).toHaveLength(0)
  expect(calls.some(url => url.endsWith(`/conversations/${conversationId}`))).toBe(true)
  expect(await page.locator('[data-conversation-id]').count()).toBe(50)
  expect(await page.locator('[data-message-id]').count()).toBe(50)
  const scroller = page.locator('.chat-scroll')
  await scroller.evaluate(element => { element.scrollTop = 0 })
  await page.getByRole('button', { name: 'Ältere Nachrichten laden', exact: true }).click()
  await expect(page.locator('[data-message-id]')).toHaveCount(100)
  const old = page.locator(`[data-message-id="${uuid(10999)}"]`)
  await old.getByRole('button', { name: 'Nächste Antwortvariante' }).click()
  await expect(page.locator('.chat-timeline')).toContainText('Alternative outside loaded branch')
  const alternative = page.locator(`[data-message-id="${uuid(20000)}"]`)
  await alternative.getByRole('button', { name: 'Vorherige Antwortvariante' }).click()
  await expect(page.locator('.chat-timeline')).toContainText('Synthetic node 1001')
  await page.reload()
  await expect(page.locator('.chat-timeline')).toContainText('Synthetic node 1001')
  const sidebarButton = page.getByRole('button', { name: 'Sidebar öffnen', exact: true })
  if (await sidebarButton.isVisible()) await sidebarButton.click()
  await page.getByRole('button', { name: 'Weitere Chats laden', exact: true }).click()
  await expect(page.getByRole('navigation', { name: 'Gespräche', exact: true }).locator('[data-conversation-id]')).toHaveCount(100)
  const search = page.getByRole('button', { name: /Suche öffnen|Chats suchen/, exact: true }).first()
  await search.click()
  await page.getByPlaceholder('Chat suchen …').fill('Sidebar chat 1')
  await expect(page.getByRole('option', { name: 'Sidebar chat 1', exact: true })).toBeVisible()
  await page.getByRole('option', { name: 'Sidebar chat 1', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Nachricht' })).toBeEnabled()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('a failed older page preserves messages and offers retry', async ({ page, request }) => {
  test.setTimeout(120000)
  await seed(request)
  await page.goto('/')
  await expect(page.locator('[data-message-id]')).toHaveCount(50)
  await page.route('**/active-path?*beforeMessageId=*', route => route.fulfill({ status: 503, json: { error: { code: 'UNAVAILABLE', message: 'Vorübergehend offline', request_id: uuid(888) } } }))
  await page.locator('.chat-scroll').evaluate(element => { element.scrollTop = 0 })
  await page.getByRole('button', { name: 'Ältere Nachrichten laden', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Vorübergehend offline')
  await expect(page.locator('[data-message-id]')).toHaveCount(50)
  await page.unroute('**/active-path?*beforeMessageId=*')
  await page.getByRole('button', { name: 'Ältere Nachrichten laden', exact: true }).click()
  await expect(page.locator('[data-message-id]')).toHaveCount(100)
})

test('keeps loaded ancestors after streaming and restores a saved reader anchor on reload', async ({ page, request }) => {
  test.setTimeout(120000)
  const conversationId = await seed(request)
  await page.goto('/')
  await expect(page.locator('[data-message-id]')).toHaveCount(50)
  const scroller = page.locator('.chat-scroll')
  await scroller.evaluate(element => { element.scrollTop = 0 })
  await page.getByRole('button', { name: 'Ältere Nachrichten laden', exact: true }).click()
  await expect(page.locator('[data-message-id]')).toHaveCount(100)
  const composer = page.getByRole('textbox', { name: 'Nachricht' })
  await composer.fill('Full context through a lazy window')
  await composer.press('Enter')
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  await expect(page.locator('[data-message-id]')).toHaveCount(102)
  await scroller.evaluate(element => { element.scrollTop = 0 })
  await page.getByRole('button', { name: 'Ältere Nachrichten laden', exact: true }).click()
  await expect(page.locator('[data-message-id]')).toHaveCount(152)
  // Save an actual visible message anchor outside the initial 50-row window.
  const anchor = uuid(10920)
  await page.locator(`[data-message-id="${anchor}"]`).scrollIntoViewIfNeeded()
  await scroller.evaluate(element => { element.dispatchEvent(new WheelEvent('wheel', { deltaY: -10 })); element.dispatchEvent(new Event('scroll')) })
  await expect.poll(() => page.evaluate(id => {
    const values = JSON.parse(localStorage.getItem('noris-ai:chat-scroll:v1') ?? '[]')
    return values.find((entry: [string, { following: boolean }]) => entry[0] === id)?.[1]?.following
  }, conversationId)).toBe(false)
  await page.reload()
  await expect(page.locator(`[data-message-id="${anchor}"]`)).toBeVisible()
  await expect(page.locator('.chat-timeline')).toContainText('Full context through a lazy window')
  expect(await scroller.evaluate(element => element.scrollTop < element.scrollHeight - element.clientHeight - 64)).toBe(true)
})
