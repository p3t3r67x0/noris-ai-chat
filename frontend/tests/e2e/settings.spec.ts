import { expect, test } from '@playwright/test'
import { savedChat, seedChat } from './chat-fixtures'
import { openDataControls } from './settings-helpers'

for (const theme of ['light', 'dark']) {
  test(`settings navigation preserves the composer, draft and reader position in ${theme}`, async ({ page }) => {
    await seedChat(page, savedChat(20), theme)
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
    await input.evaluate(element => { element.dataset.instance = 'original' })
    await input.fill('Synthetischer Entwurf bleibt erhalten')
    const position = await page.locator('.chat-scroll').evaluate(element => {
      element.scrollTop = 100; element.dispatchEvent(new Event('scroll')); return element.scrollTop
    })
    await expect(page.locator('.chat-main').getByText('Lokale Chats importieren', { exact: true })).toHaveCount(0)
    const settings = await openDataControls(page)
    await expect(settings.getByRole('button', { name: 'Importieren', exact: true })).toHaveCount(0)
    await settings.getByRole('tab', { name: 'Allgemein', exact: true }).click()
    await expect(settings.getByRole('button', { name: 'Darstellung in den Einstellungen' })).toBeVisible()
    expect(await settings.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
    await page.keyboard.press('Escape')
    await expect(settings).not.toBeVisible()
    await expect(input).toHaveAttribute('data-instance', 'original')
    await expect(input).toHaveValue('Synthetischer Entwurf bleibt erhalten')
    expect(await page.locator('.chat-scroll').evaluate(element => element.scrollTop)).toBe(position)
    await input.focus()
    await expect(input).toBeFocused()
    expect(await page.evaluate(() => scrollY === 0 && document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })

  test(`composer and footer stay fixed through streaming and keyboard resizing in ${theme}`, async ({ page }) => {
    await seedChat(page, savedChat(20), theme)
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
    await input.evaluate(element => { element.dataset.instance = 'original' })
    await input.fill('/lang')
    const before = await page.locator('.composer-dock').boundingBox()
    await page.clock.install()
    await page.clock.pauseAt(new Date(await page.evaluate(() => Date.now()) + 100))
    await input.press('Enter')
    for (const elapsed of [1000, 1500]) {
      await page.clock.runFor(elapsed)
      await expect(page.locator('[data-generation-status]')).toHaveAttribute('data-generation-status', 'streaming')
      expect(await page.locator('.composer-dock').boundingBox()).toEqual(before)
      await expect(input).toBeFocused()
      await expect(input).toHaveAttribute('data-instance', 'original')
    }
    const position = await page.locator('.chat-scroll').evaluate(element => {
      element.scrollTop = 0; element.dispatchEvent(new Event('scroll')); return element.scrollTop
    })
    for (const height of [420, 250, 420]) {
      await page.evaluate(value => {
        const viewport = window.visualViewport!
        Object.defineProperty(viewport, 'height', { configurable: true, value })
        Object.defineProperty(viewport, 'offsetTop', { configurable: true, value: 20 })
        viewport.dispatchEvent(new Event('resize'))
      }, height)
      await page.clock.runFor(100)
      const composer = (await page.locator('.chat-composer').boundingBox())!
      const note = (await page.locator('.composer-note').boundingBox())!
      expect(note.y).toBeGreaterThan(composer.y + composer.height)
      expect(note.y + note.height).toBeLessThanOrEqual(height + 20)
      await expect(input).toBeFocused()
      expect(await page.locator('.chat-scroll').evaluate(element => element.scrollTop)).toBe(position)
      expect(await page.evaluate(() => scrollY === 0 && document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      expect(await page.locator('.composer-dock').evaluate(element => element.scrollHeight <= element.clientHeight)).toBe(true)
    }
    await page.getByRole('button', { name: 'Antwort stoppen', exact: true }).click()
    await page.clock.runFor(100)
    await expect(input).toBeFocused()
  })
}
