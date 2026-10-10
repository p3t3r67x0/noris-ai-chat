import { expect, test } from '@playwright/test'
import { savedChat, seedChat } from '../e2e/chat-fixtures'
import { openDataControls } from '../e2e/settings-helpers'

for (const theme of ['light', 'dark']) {
  test(`SSE settings omit database import even with local chats in ${theme}`, async ({ page }) => {
    let imports = 0
    page.on('request', request => { if (request.url().endsWith('/conversations/import') && request.method() === 'POST') imports++ })
    await seedChat(page, savedChat(), theme)
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    await expect(page.locator('.chat-message')).toHaveCount(2)
    await expect(page.locator('.chat-main').getByText('Lokale Chats importieren', { exact: true })).toHaveCount(0)
    const settings = await openDataControls(page)
    await expect(settings.getByRole('button', { name: 'Importieren', exact: true })).toHaveCount(0)
    await expect(settings).toContainText('Hier sind derzeit keine Datenaktionen verfügbar.')
    expect(imports).toBe(0)
  })
}
