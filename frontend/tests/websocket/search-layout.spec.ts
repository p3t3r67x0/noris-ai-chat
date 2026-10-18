import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'
import { clearTestConversations, stableModelCatalog } from './chat-fixtures'
import type { ApiSchemas } from '../../app/types/generated/api'

test('search keeps loading, errors, retry and pagination in the existing server pipeline', async ({ page, request }) => {
  await clearTestConversations(request)
  const conversations: ApiSchemas['ImportConversation'][] = []
  const messages: ApiSchemas['ImportMessage'][] = []
  for (let index = 0; index < 55; index++) {
    const id = randomUUID(), messageId = randomUUID()
    const date = new Date(Date.UTC(2026, 9, 9, 12, index)).toISOString()
    conversations.push({ id, title: `Synthetischer Treffer ${index}`, titleSource: 'manual', createdAt: date, updatedAt: date, activeLeafMessageId: messageId })
    messages.push({ id: messageId, conversationId: id, parentMessageId: null, role: 'user', content: 'Layoutnadel: ' + 'Sicherer mehrzeiliger Textauszug. '.repeat(12), status: 'completed', createdAt: date, updatedAt: date })
  }
  expect((await request.post('/api/v1/conversations/import', { data: { conversations, messages, activeConversationId: conversations[0]!.id } })).ok()).toBe(true)
  expect((await request.put('/api/v1/chat/preferences', { data: { activeConversationId: conversations[0]!.id, modelId: 'fixture-alpha' } })).ok()).toBe(true)
  await stableModelCatalog(page)
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  let hold = true, fail = false
  const requests: URL[] = []
  await page.route('**/api/v1/conversations?**', async route => {
    const url = new URL(route.request().url())
    if (url.searchParams.get('q') === 'Layoutnadel') {
      requests.push(url)
      if (hold) await gate
      if (fail) { await route.fulfill({ status: 503, json: { detail: 'Synthetic unavailable' } }); return }
    }
    await route.continue()
  })
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await page.keyboard.press('Control+k')
  const dialog = page.locator('.chat-search-dialog'), input = dialog.locator('input')
  await expect(dialog.getByRole('option')).toHaveCount(50)
  await input.fill('Layoutnadel')
  await expect(dialog.locator('.chat-search-loading .iconify')).toBeVisible()
  hold = false; fail = true; release()
  await expect(dialog.getByRole('alert')).toContainText('Der Chatdienst ist momentan nicht bereit')
  await expect(dialog).not.toContainText('Synthetic unavailable')
  fail = false
  await dialog.getByRole('button', { name: 'Suche erneut versuchen', exact: true }).click()
  await expect(dialog.getByRole('alert')).toHaveCount(0)
  await expect(dialog.locator('.chat-search-row-excerpt')).toHaveCount(50)
  await expect(dialog.getByRole('button', { name: 'Weitere Chats laden', exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: 'Weitere Chats laden', exact: true }).click()
  await expect(dialog.getByRole('option')).toHaveCount(55)
  expect(requests.some(url => url.searchParams.has('cursor'))).toBe(true)
  const rows = await dialog.getByRole('option').evaluateAll(elements => elements.map(row => {
    const title = row.querySelector('.chat-search-row-title')!.getBoundingClientRect()
    const excerpt = row.querySelector('.chat-search-row-excerpt')!.getBoundingClientRect()
    return { row: row.getBoundingClientRect().toJSON(), title: title.toJSON(), excerpt: excerpt.toJSON() }
  }))
  for (let index = 0; index < rows.length; index++) {
    expect(rows[index]!.title.bottom).toBeLessThanOrEqual(rows[index]!.excerpt.top)
    if (index) expect(rows[index - 1]!.row.bottom).toBeLessThanOrEqual(rows[index]!.row.top)
  }
  await input.fill('keinVorhandenerTreffer')
  await expect(dialog.getByText('Keine Chats gefunden', { exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: 'Löschen', exact: true }).click()
  await expect(input).toBeFocused()
  await expect(input).toHaveValue('')
  await expect(dialog.getByRole('option')).toHaveCount(50)
})
