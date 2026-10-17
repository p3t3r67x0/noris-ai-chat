import { expect, test } from '@playwright/test'
import { savedChat, seedChat } from './chat-fixtures'

test.use({ deviceScaleFactor: 1 })
// Three screenshot states plus repeated resize/focus checks exceed 30s on shared runners.
test.setTimeout(60_000)
for (const viewport of [{ width: 1701, height: 863 }, { width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  for (const theme of ['light', 'dark']) {
    test(`adaptive composer ${viewport.width} ${theme}`, async ({ page }) => {
      await page.setViewportSize(viewport)
      await seedChat(page, savedChat(20), theme)
      await page.goto('/')
      await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      const composer = page.locator('.chat-composer')
      const layout = page.locator('.composer-container')
      const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
      await input.focus()
      await input.evaluate(element => { element.dataset.instance = 'original' })
      const original = (await composer.boundingBox())!
      const send = (await page.locator('.composer-submit').boundingBox())!
      async function geometry(): Promise<void> {
        const box = (await composer.boundingBox())!
        expect(box.y + box.height).toBeCloseTo(original.y + original.height, 0)
        for (const selector of ['.composer-attachment', '.composer-submit']) {
          const button = (await page.locator(selector).boundingBox())!
          expect(button.y + button.height / 2).toBeCloseTo(send.y + send.height / 2, 0)
        }
        await expect(input).toBeFocused()
        await expect(input).toHaveAttribute('data-instance', 'original')
        expect(await page.evaluate(() => scrollY === 0 && document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      }
      for (const value of ['', 'Wort', 'Kurze Frage']) {
        await input.fill(value)
        await expect(layout).toHaveAttribute('data-layout', 'compact')
        await geometry()
      }
      await expect(page).toHaveScreenshot(`adaptive-${viewport.width}-compact-${theme}.png`, { animations: 'disabled', caret: 'hide' })
      await input.fill('Dieser Satz braucht zusätzlichen Platz. '.repeat(8))
      await expect(layout).not.toHaveAttribute('data-layout', 'compact')
      await geometry()
      for (const lines of [2, 5, 10]) {
        await input.fill(Array.from({ length: lines }, (_, i) => `Synthetische Zeile ${i + 1}`).join('\n'))
        await expect(layout).not.toHaveAttribute('data-layout', 'compact')
        await geometry()
      }
      await input.fill('Erste Zeile\nZweite Zeile\nDritte Zeile\nVierte Zeile')
      await expect(layout).toHaveAttribute('data-layout', 'expanded')
      await geometry()
      await expect(page).toHaveScreenshot(`adaptive-${viewport.width}-expanded-${theme}.png`, { animations: 'disabled', caret: 'hide' })
      await input.fill('Sehr langer synthetischer Paste. '.repeat(500))
      await expect(layout).toHaveAttribute('data-layout', 'maximized')
      expect(await input.evaluate(element => element.scrollHeight > element.clientHeight && getComputedStyle(element).overflowY === 'auto' && element.scrollWidth <= element.clientWidth)).toBe(true)
      await geometry()
      await expect(page).toHaveScreenshot(`adaptive-${viewport.width}-maximized-${theme}.png`, { animations: 'disabled', caret: 'hide' })
      await input.fill('')
      await expect(layout).toHaveAttribute('data-layout', 'compact')
      expect(await composer.boundingBox()).toEqual(original)
      await geometry()
      await input.fill('Cursor bleibt erhalten')
      await input.evaluate(element => (element as HTMLTextAreaElement).setSelectionRange(3, 3))
      await page.evaluate(() => document.documentElement.style.setProperty('zoom', '1.25'))
      await expect(input).toBeFocused()
      expect(await input.evaluate(element => (element as HTMLTextAreaElement).selectionStart)).toBe(3)
      await input.fill('Umbruch bei vergrößerter Darstellung. '.repeat(12))
      await expect(layout).not.toHaveAttribute('data-layout', 'compact')
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    })
  }
}
