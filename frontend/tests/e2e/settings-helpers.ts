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
  await page.getByRole('button', { name: 'Einstellungen', exact: true }).click()
  const settings = page.getByRole('dialog', { name: 'Einstellungen', exact: true })
  await expect(settings).toBeVisible()
  await settings.getByRole('tab', { name: 'Datenkontrollen', exact: true }).click()
  return settings
}
