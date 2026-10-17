import { expect, test, type Page } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { savedChat, seedChat } from './chat-fixtures'
import { openSettingsCategory, returnToChat } from './settings-helpers'
import { CHAT_STORAGE_KEY } from '../../app/lib/chat/persistence'

async function openSidebar(page: Page) {
  const toggle = page.getByRole('button', { name: 'Sidebar öffnen', exact: true })
  if (await toggle.isVisible()) await toggle.click()
  await expect(page.getByRole('navigation', { name: 'Gespräche', exact: true })).toBeVisible()
}

test('Settings keeps tab-conflict recovery available after the warning toast closes', async ({ page, context }) => {
  await page.clock.install()
  await seedChat(page, savedChat())
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const draft = 'Synthetischer Entwurf bleibt beim erneuten Einlesen erhalten'
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).fill(draft)
  await expect.poll(() => page.evaluate(key => JSON.parse(localStorage.getItem(key)!).drafts.main, CHAT_STORAGE_KEY)).toBe(draft)
  await openProfileSettings(page)
  await openSettingsCategory(page, 'Datensicherung')
  const otherTab = await context.newPage()
  await otherTab.goto('/api/v1/health/live')
  await otherTab.evaluate(key => {
    const snapshot = JSON.parse(localStorage.getItem(key)!)
    snapshot.conversations.conversations.main.title = 'Synthetische Titeländerung im anderen Tab'
    localStorage.setItem(key, JSON.stringify(snapshot))
  }, CHAT_STORAGE_KEY)
  await otherTab.close()
  await expect(page.locator('[data-persistence-state]')).toHaveText('Speicherung pausiert')
  await expect(page.locator('.app-notification')).toContainText('anderen Tab')
  await page.clock.runFor(8000)
  await expect(page.locator('.app-notification')).toHaveCount(0)
  const reload = page.locator('[data-backup-settings]').getByRole('button', { name: 'Seite neu laden', exact: true })
  await reload.focus()
  await reload.press('Enter')
  await expect(page.locator('[data-persistence-state]')).toHaveText('Speicherung aktiv')
  await returnToChat(page)
  await expect(page.getByRole('textbox', { name: 'Nachricht', exact: true })).toHaveValue(draft)
})

async function openProfileSettings(page: Page) {
  if (await page.evaluate(() => innerWidth < 1024)) await openSidebar(page)
  await page.locator('.profile-trigger:visible').click()
  await page.getByRole('menuitem', { name: 'Einstellungen', exact: true }).click()
  await expect(page).toHaveURL(/\/settings\/general$/)
}

for (const theme of ['light', 'dark']) {
  test(`settings-only controls and recovery status in ${theme}`, async ({ page }, info) => {
    // The complete chat/settings/recovery screenshot sequence exceeds 30s on
    // the shared browser host. Keep individual assertions and pixel limits.
    test.setTimeout(60_000)
    const width = info.project.name === 'mobile' ? 390 : 1440
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 })
    await page.emulateMedia({ colorScheme: theme as 'light' | 'dark', reducedMotion: 'reduce' })
    await seedChat(page, savedChat(), theme)
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
    await input.fill('Synthetischer Entwurf für die Datensicherung')
    await expect.poll(() => page.evaluate(key => JSON.parse(localStorage.getItem(key)!).drafts.main, CHAT_STORAGE_KEY)).toBe('Synthetischer Entwurf für die Datensicherung')
    const root = resolve('../docs/ui-reference/settings-only')
    await mkdir(root, { recursive: true })
    const capture = async (name: string) => {
      await expect(page).toHaveScreenshot(`settings-only-${theme}-${name}.png`, { animations: 'disabled', caret: 'hide' })
      await writeFile(resolve(root, `${width}-${theme}-${name}.png`), await page.screenshot({ animations: 'disabled', caret: 'hide' }))
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    }
    await openSidebar(page)
    await expect(page.getByLabel('Darstellung', { exact: true })).toHaveCount(0)
    if (width >= 1024) await expect(page.locator('.conversation-sidebar [data-slot="footer"]')).toBeHidden()
    await capture('chat-open')
    await page.getByRole('button', { name: 'Gesprächsliste schließen', exact: true }).click()
    await expect(page.getByRole('navigation', { name: 'Gespräche', exact: true })).toBeHidden()
    await expect(page.locator('.chat-main')).not.toContainText('Sicherung und Änderungen prüfen')
    await capture('chat-closed')
    await openProfileSettings(page)
    const appearance = page.getByRole('combobox', { name: 'Darstellung Einstellungen', exact: true })
    await expect(appearance).toBeVisible()
    await capture('appearance')
    for (const [label, value] of [['Dunkel', 'dark'], ['Hell', 'light'], ['System', 'system']] as const) {
      await appearance.click()
      await page.getByRole('option', { name: label, exact: true }).click()
      await expect.poll(() => page.evaluate(() => localStorage.getItem('noris-ai-theme'))).toBe(value)
      await expect(page.locator('html')).toHaveClass(new RegExp(value === 'system' ? theme : value))
      await page.reload()
      await expect(appearance).toContainText(label)
    }
    await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' })
    await expect(page.locator('html')).toHaveClass(/dark/)
    await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' })
    await expect(page.locator('html')).toHaveClass(/light/)
    await appearance.click()
    await page.getByRole('option', { name: theme === 'dark' ? 'Dunkel' : 'Hell', exact: true }).click()
    await openSettingsCategory(page, 'Datensicherung')
    await expect(page.locator('[data-persistence-state]')).toHaveText('Speicherung aktiv')
    await expect(page.locator('[data-restored-drafts]')).toHaveText('1')
    await expect(page.locator('[data-failed-operations]')).toHaveText('0')
    await capture('backup')
    await returnToChat(page)
    await expect(input).toHaveValue('Synthetischer Entwurf für die Datensicherung')
    await expect(page.locator('.chat-main')).not.toContainText('Sicherung und Änderungen prüfen')
  })
}
