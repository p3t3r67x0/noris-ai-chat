import { expect, test } from '@playwright/test'

test('search owns keyboard focus without cancelling a response or changing its conversation', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const composer = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await composer.fill('/lang')
  await composer.press('Enter')
  const status = page.locator('[data-generation-status]')
  await expect(status).toHaveAttribute('data-generation-status', 'streaming')
  const question = await page.locator('.message-user').getAttribute('data-message-id')
  await page.keyboard.press('Control+k')
  const dialog = page.getByRole('dialog', { name: 'Chats suchen', exact: true })
  const input = dialog.getByPlaceholder('Suchen...')
  await expect(input).toBeFocused()
  await page.evaluate(() => {
    const input = document.getElementById('chat-search-input')!
    const observe = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'o') {
        input.dataset.shortcutPrevented = String(event.defaultPrevented)
        window.removeEventListener('keydown', observe)
      }
    }
    window.addEventListener('keydown', observe)
  })
  await input.press('Control+Shift+o')
  await expect(input).toHaveAttribute('data-shortcut-prevented', 'true')
  await expect(dialog).toBeVisible()
  await expect(page.locator('.message-user')).toHaveAttribute('data-message-id', question!)
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await expect(composer).toBeFocused()
  await expect(status).toHaveAttribute('data-generation-status', 'streaming')
  await page.getByRole('button', { name: 'Antwort stoppen', exact: true }).click()
  await expect(status).toHaveAttribute('data-generation-status', 'cancelled')
})

test('the modal covers the rail and keeps its close control above the resized workspace', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 975 })
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await page.keyboard.press('Control+k')
  const overlay = page.locator('.chat-search-overlay')
  const dialog = page.getByRole('dialog', { name: 'Chats suchen', exact: true })
  await expect(dialog).toBeVisible()
  const railLayer = await page.locator('.chat-rail').evaluate(el => Number(getComputedStyle(el).zIndex))
  const overlayLayer = await overlay.evaluate(el => Number(getComputedStyle(el).zIndex))
  expect(overlayLayer).toBeGreaterThan(railLayer)
  expect(await dialog.evaluate(el => Number(getComputedStyle(el).zIndex))).toBeGreaterThan(overlayLayer)
  await page.setViewportSize({ width: 390, height: 320 })
  const close = dialog.getByRole('button', { name: 'Suche schließen' })
  const box = (await close.boundingBox())!
  expect(await page.evaluate(({ x, y }) => Boolean(document.elementFromPoint(x, y)?.closest('.chat-search-close')), { x: box.x + box.width / 2, y: box.y + box.height / 2 })).toBe(true)
  await close.click()
  await expect(dialog).not.toBeVisible()
})
