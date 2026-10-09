import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

async function send(page: Page, text: string) {
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.fill(text); await input.press('Enter')
  await expect(page.locator('[data-generation-status]')).toHaveAttribute('data-generation-status', 'completed', { timeout: 10_000 })
}
test.beforeEach(async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true', { timeout: 15_000 })
})

test('edit branches preserve the original question and its continuation', async ({ page }) => {
  await send(page, 'Originale Frage')
  await send(page, 'Weitere Frage')
  await page.getByRole('button', { name: 'Nachricht bearbeiten', exact: true }).first().click()
  const dialog = page.getByRole('dialog', { name: 'Nachricht bearbeiten', exact: true })
  await dialog.getByRole('textbox', { name: 'Nachricht bearbeiten', exact: true }).fill('Bearbeitete Frage')
  await dialog.getByRole('button', { name: 'Speichern und senden' }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.locator('[data-generation-status]')).toHaveAttribute('data-generation-status', 'completed')
  await expect(page.locator('.message-user')).toHaveCount(1)
  await expect(page.locator('.message-user')).toContainText('Bearbeitete Frage')
  await page.getByRole('button', { name: 'Vorherige Fragevariante' }).click()
  await expect(page.locator('.message-user')).toHaveCount(2)
  await expect(page.locator('.message-user').first()).toContainText('Originale Frage')
  await page.getByRole('button', { name: 'Nächste Fragevariante' }).click()
  await expect(page.locator('.message-user')).toHaveCount(1)
  await expect(page.locator('.message-user')).toContainText('Bearbeitete Frage')
})

test('regeneration creates a separate answer and keeps selected variants after reload', async ({ page }) => {
  await send(page, 'Eine Frage')
  const first = await page.locator('.message-assistant').getAttribute('data-message-id')
  await page.getByRole('button', { name: 'Antwort erneut generieren', exact: true }).click()
  await expect(page.locator('[data-generation-status]')).toHaveAttribute('data-generation-status', 'completed')
  const second = await page.locator('.message-assistant').getAttribute('data-message-id')
  expect(second).not.toBe(first)
  await page.getByRole('button', { name: 'Vorherige Antwortvariante' }).click()
  await expect(page.locator('.message-assistant')).toHaveAttribute('data-message-id', first!)
  await page.reload()
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await expect(page.locator('.message-assistant')).toHaveAttribute('data-message-id', first!)
  await page.getByRole('button', { name: 'Nächste Antwortvariante' }).click()
  await expect(page.locator('.message-assistant')).toHaveAttribute('data-message-id', second!)
})

test('conversation drafts survive switching and a page reload', async ({ page }) => {
  await send(page, 'Erstes Gespräch')
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.fill('Entwurf im ersten Chat')
  const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
  if (await toggle.getAttribute('aria-expanded') === 'true') await toggle.click()
  await page.locator('.chat-header').getByRole('button', { name: 'Neuer Chat', exact: true }).click()
  await expect(input).toHaveValue('')
  await input.fill('Entwurf im zweiten Chat')
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  await page.getByRole('navigation', { name: 'Gespräche' }).getByRole('button', { name: 'Lokales Chat-Beispiel', exact: true }).click()
  await expect(input).toHaveValue('Entwurf im ersten Chat')
  await page.reload()
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await expect(input).toHaveValue('Entwurf im ersten Chat')
})
