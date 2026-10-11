import { expect } from '@playwright/test'
import type { Page } from '@playwright/test'

export async function openDataControls(page: Page) {
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  if (await page.evaluate(() => matchMedia('(min-width: 1024px)').matches)) {
    await page.locator('.chat-rail').getByRole('button', { name: /^(Dein|Lokaler) Arbeitsbereich$/ }).click()
  }
  else {
    await page.getByRole('button', { name: 'Sidebar öffnen', exact: true }).click()
  }
  if (await page.locator('.profile-menu').isVisible()) await page.getByRole('menuitem', { name: 'Einstellungen', exact: true }).click()
  else await page.getByRole('button', { name: 'Einstellungen', exact: true }).click()
  const settings = page.getByRole('main', { name: 'Einstellungen', exact: true })
  await expect(settings).toBeVisible()
  await openSettingsCategory(page, 'Datenkontrollen')
  return settings
}

export async function openSettingsCategory(page: Page, name: string) {
  const toggle = page.locator('.settings-mobile-toggle')
  if (await toggle.isVisible() && await toggle.getAttribute('aria-expanded') === 'false') {
    await toggle.click()
    await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  }
  await page.locator('.settings-sidebar').getByRole('link', { name, exact: true }).click()
  // Finish this route transition before the next call can reopen mobile navigation.
  await expect(page.getByRole('main', { name: 'Einstellungen', exact: true }).getByRole('heading', { name, exact: true, level: 1 })).toBeVisible()
}

export async function returnToChat(page: Page) {
  const toggle = page.locator('.settings-mobile-toggle')
  if (await toggle.isVisible() && await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  await page.getByRole('link', { name: 'Zurück zum Chat', exact: true }).click()
  await expect(page).toHaveURL(/\/$/)
}
