import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'
import { clearTestConversations, stableModelCatalog } from './chat-fixtures'
import type { ApiSchemas } from '../../app/types/generated/api'

test('message search loads an older page, navigates to its target and preserves the draft', async ({ page, request }) => {
  await clearTestConversations(request)
  const id = randomUUID()
  const messages: ApiSchemas['ImportMessage'][] = []
  for (let index = 0; index < 80; index++) {
    const createdAt = new Date(Date.UTC(2026, 9, 9, 12, index)).toISOString()
    messages.push({ id: randomUUID(), conversationId: id, parentMessageId: messages.at(-1)?.id ?? null, role: index % 2 ? 'assistant' : 'user', content: index === 1 ? 'Synthetischer Regenbogenarchiv Treffer in einer älteren Antwort.' : `Neutraler Testbeitrag ${index}`, status: 'completed', createdAt, updatedAt: createdAt })
  }
  const imported = await request.post('/api/v1/conversations/import', { data: {
    conversations: [{ id, title: 'Synthetischer Verlauf', titleSource: 'manual', createdAt: messages[0]!.createdAt, updatedAt: messages.at(-1)!.createdAt, activeLeafMessageId: messages.at(-1)!.id }],
    messages, activeConversationId: id, drafts: { [id]: 'Mein gespeicherter Entwurf' },
  } })
  expect(imported.ok()).toBe(true)
  // Import respects existing preferences; explicitly choose this fixture in
  // each project instead of depending on whether the account imported before.
  expect((await request.put('/api/v1/chat/preferences', { data: { activeConversationId: id, modelId: 'fixture-alpha' } })).ok()).toBe(true)
  await stableModelCatalog(page)
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const input = page.locator('.composer-input')
  await expect(input).toHaveValue('Mein gespeicherter Entwurf')
  const target = page.locator(`[data-message-id="${messages[1]!.id}"]`)
  await expect(target).toHaveCount(0)
  await page.keyboard.press('Control+k')
  const search = page.getByRole('combobox', { name: 'Chats suchen', exact: true })
  await search.fill('Regenbogenarchiv')
  const option = page.getByRole('option', { name: /Synthetischer Verlauf/ })
  await expect(option).toContainText('Regenbogenarchiv')
  await search.press('ArrowDown')
  await search.press('Enter')
  await expect(target).toBeInViewport()
  await expect(target).toBeFocused()
  await expect(input).toHaveValue('Mein gespeicherter Entwurf')
})
