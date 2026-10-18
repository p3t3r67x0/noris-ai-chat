import { expect, test } from '@playwright/test'
import { seedLoadingChats } from './loading-fixtures'

for (const target of ['10000000-0000-4000-8000-999999999999', '../invalid']) {
  test(`New Chat recovers from unavailable direct target ${target}`, async ({ page, request }) => {
    await seedLoadingChats(page, request)
    await page.goto(`/?conversationId=${encodeURIComponent(target)}`)
    await expect(page.locator('.chat-message-pane').getByRole('alert')).toContainText('Chat konnte nicht geladen werden.')
    await page.keyboard.press('Control+Shift+O')
    await expect(page.getByRole('status', { name: 'Chat wird geladen', exact: true })).toHaveCount(0)
    await expect(page.locator('.chat-message-pane').getByRole('alert')).toHaveCount(0)
    await expect(page.locator('.empty-chat')).toBeVisible()
    await expect(page.locator('.chat-message')).toHaveCount(0)
    expect(new URL(page.url()).searchParams.has('conversationId')).toBe(false)
    await page.locator('.composer-input').fill('Ein neuer synthetischer Entwurf')
    await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
    await expect.poll(async () => (await (await request.get('/api/v1/chat/preferences')).json()).activeConversationId).toBeNull()
    await expect.poll(async () => (await (await request.get('/api/v1/chat/drafts?keys=__new__')).json()).drafts.find((draft: { key: string, content: string }) => draft.key === '__new__')?.content).toBe('Ein neuer synthetischer Entwurf')
    await page.reload()
    await expect(page.locator('.empty-chat')).toBeVisible()
    await expect(page.locator('.composer-input')).toHaveValue('Ein neuer synthetischer Entwurf')
  })
}
