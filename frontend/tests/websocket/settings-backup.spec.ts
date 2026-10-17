import { expect, test, type Page } from '@playwright/test'
import { notificationBackend } from '../notifications/fixtures'
import { openDataControls, openSettingsCategory, returnToChat } from '../e2e/settings-helpers'

async function ready(page: Page) {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await expect(page.locator('.message-assistant')).toHaveCount(1)
}

test('recovered server drafts stay intact and informational backup notices appear only in Settings', async ({ page }) => {
  const state = await notificationBackend(page, { restoredDraft: true })
  await ready(page)
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await expect(input).toHaveValue('Ein wiederhergestellter Entwurf.')
  await expect(page.locator('.app-notification')).toHaveCount(0)
  await expect(page.locator('.chat-main')).not.toContainText('Sicherung und Änderungen prüfen')
  await openDataControls(page)
  await openSettingsCategory(page, 'Datensicherung')
  await expect(page.locator('[data-restored-drafts]')).toHaveText('1')
  await expect(page.locator('[data-backup-settings]')).toContainText('Ein lokal noch nicht gespeicherter Entwurf wurde wiederhergestellt.')
  await expect.poll(() => state.savedDraft).toBe('Ein wiederhergestellter Entwurf.')
  await returnToChat(page)
  await expect(input).toHaveValue('Ein wiederhergestellter Entwurf.')
})

test('critical save errors remain visible and Settings retries the latest unsaved draft', async ({ page }) => {
  const state = await notificationBackend(page, { failDrafts: 1 })
  await ready(page)
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.fill('Nicht gespeicherter synthetischer Entwurf')
  await expect(page.locator('.app-notification')).toContainText('Entwurf konnte nicht gespeichert werden.')
  await expect(page.locator('.chat-main')).not.toContainText('Sicherung und Änderungen prüfen')
  await openDataControls(page)
  await openSettingsCategory(page, 'Datensicherung')
  await expect(page.locator('[data-failed-operations]')).toHaveText('1')
  await expect(page.locator('[data-pending-drafts]')).toHaveText('1')
  await expect(page.locator('[data-backup-settings]')).toContainText('Letzter bekannter Speicherfehler')
  await page.locator('[data-backup-settings]').getByRole('button', { name: 'Erneut speichern', exact: true }).click()
  await expect(page.locator('[data-failed-operations]')).toHaveText('0')
  await expect(page.locator('[data-pending-drafts]')).toHaveText('0')
  expect(state.savedDraft).toBe('Nicht gespeicherter synthetischer Entwurf')
  await expect(page.locator('[data-backup-settings]')).toContainText('Letzter bekannter Speicherfehler')
  await returnToChat(page)
  await expect(input).toHaveValue('Nicht gespeicherter synthetischer Entwurf')
})
