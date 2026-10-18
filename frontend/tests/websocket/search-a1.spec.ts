import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'
import { clearTestConversations, stableModelCatalog } from './chat-fixtures'
import { returnToChat } from '../e2e/settings-helpers'
import type { ApiSchemas } from '../../app/types/generated/api'

test('ranked AND search pages archived pins and preserves the active chat draft', async ({ page, request }) => {
  await clearTestConversations(request)
  const conversations: ApiSchemas['ImportConversation'][] = []
  const messages: ApiSchemas['ImportMessage'][] = []
  for (let index = 0; index < 57; index++) {
    const id = randomUUID(), messageId = randomUUID()
    const createdAt = new Date(Date.UTC(2026, 0, 1, 0, index)).toISOString()
    conversations.push({ id, title: index === 0 ? 'Docker healthcheck Phrase' : index === 55 ? 'Active Docker' : `Docker Archiv ${index}`, titleSource: 'manual', createdAt, updatedAt: createdAt, activeLeafMessageId: messageId, archivedAt: index === 55 ? null : createdAt, pinnedAt: index < 55 ? createdAt : null })
    messages.push({ id: messageId, conversationId: id, parentMessageId: null, role: 'user', content: `healthcheck Testbeitrag ${index}`, status: 'completed', createdAt, updatedAt: createdAt })
  }
  const active = conversations[55]!
  expect((await request.post('/api/v1/conversations/import', { data: { conversations, messages, drafts: { [active.id]: 'Erhaltener Entwurf' } } })).ok()).toBe(true)
  expect((await request.put('/api/v1/chat/preferences', { data: { activeConversationId: active.id, modelId: 'fixture-alpha' } })).ok()).toBe(true)
  await stableModelCatalog(page)
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await expect(page.locator('.composer-input')).toHaveValue('Erhaltener Entwurf')
  await page.keyboard.press('Control+k')
  const dialog = page.locator('.chat-search-dialog')
  const input = dialog.getByRole('combobox', { name: 'Chats suchen', exact: true })
  await input.fill('docker healthcheck')
  await expect(dialog.getByRole('option')).toHaveCount(1)
  await dialog.getByRole('button', { name: 'Suchfilter', exact: true }).click()
  await page.getByRole('combobox', { name: 'Chat-Status', exact: true }).click()
  await page.getByRole('option', { name: 'Archivierte Chats', exact: true }).click()
  await page.getByRole('combobox', { name: 'Angeheftete Chats', exact: true }).click()
  await page.getByRole('option', { name: 'Nur angeheftete Chats', exact: true }).click()
  await expect(dialog.getByRole('button', { name: 'Suchfilter', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.chat-search-filter-panel')).toHaveScreenshot('search-a1-filters.png')
  await dialog.getByRole('button', { name: 'Suchfilter', exact: true }).click()
  await expect(dialog.getByRole('option')).toHaveCount(50)
  await expect(dialog.getByRole('option').first()).toContainText('Docker healthcheck Phrase')
  await dialog.getByRole('button', { name: 'Weitere Chats laden', exact: true }).click()
  await expect(dialog.getByRole('option')).toHaveCount(55)
  await expect(dialog.getByRole('option').first()).toContainText('Docker healthcheck Phrase')
  await dialog.getByRole('option').first().click()
  await expect(page).toHaveURL(new RegExp(`/settings/archived#archive-${conversations[0]!.id}$`))
  await expect(page.getByRole('button', { name: 'Docker healthcheck Phrase wiederherstellen', exact: true })).toBeFocused()
  expect((await (await request.get(`/api/v1/conversations/${conversations[0]!.id}`)).json()).archivedAt).toBeTruthy()
  // The oldest target is outside the first archive page. Reload drops search
  // metadata and exercises the existing authorized single-conversation fetch.
  await page.reload()
  await expect(page.getByRole('button', { name: 'Docker healthcheck Phrase wiederherstellen', exact: true })).toBeFocused()
  await returnToChat(page)
  await expect(page.locator('.composer-input')).toHaveValue('Erhaltener Entwurf')
})

test('Unicode search highlights original graphemes and filter focus returns safely', async ({ page, request }) => {
  await clearTestConversations(request)
  const id = randomUUID(), messageId = randomUUID(), createdAt = '2026-01-01T00:00:00Z'
  expect((await request.post('/api/v1/conversations/import', { data: {
    conversations: [{ id, title: 'Straße', titleSource: 'manual', createdAt, updatedAt: createdAt, activeLeafMessageId: messageId }],
    messages: [{ id: messageId, conversationId: id, parentMessageId: null, role: 'user', content: 'A\u0308pfel im gespeicherten Chat', status: 'completed', createdAt, updatedAt: createdAt }],
  } })).ok()).toBe(true)
  await stableModelCatalog(page)
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await page.locator('.composer-input').focus()
  await page.keyboard.press('Control+k')
  const dialog = page.locator('.chat-search-dialog')
  await dialog.getByRole('combobox', { name: 'Chats suchen', exact: true }).fill('STRASSE ÄPFEL')
  await expect(dialog.getByRole('option')).toHaveCount(1)
  await expect(dialog.locator('.chat-search-row-title mark')).toHaveText('Straße')
  await expect(dialog.locator('.chat-search-row-excerpt mark')).toHaveText('Äpfel')
  const filters = dialog.getByRole('button', { name: 'Suchfilter', exact: true })
  await filters.click()
  await expect(page.getByRole('combobox', { name: 'Chat-Status', exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeVisible()
  await expect(filters).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(page.locator('.composer-input')).toBeFocused()
})
