import { expect, test } from '@playwright/test'

test('the menu explains unavailable uploads in the local demo and preserves the draft', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  const trigger = page.getByRole('button', { name: 'Anhänge und Werkzeuge', exact: true })
  await input.fill('Mein Entwurf bleibt erhalten')
  await trigger.click()
  const menu = page.locator('.composer-plus-menu')
  await expect(menu.getByRole('menuitem')).toHaveCount(7)
  await expect(menu.getByRole('menuitem', { name: /^Fotos und Dateien/ })).toHaveAttribute('aria-disabled', 'true')
  await expect(menu).toContainText('Datei-Upload ist im lokalen Demo-Modus nicht verfügbar.')
  await expect(menu.getByText('Noch nicht verfügbar', { exact: true })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await expect(menu).toBeHidden()
  await expect(trigger).toBeFocused()
  await expect(input).toHaveValue('Mein Entwurf bleibt erhalten')
})
