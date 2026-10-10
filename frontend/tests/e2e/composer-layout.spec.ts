import { expect, test } from '@playwright/test'
import { savedChat, seedChat } from './chat-fixtures'

const viewports = [
  { width: 1920, height: 975 }, { width: 1701, height: 863 },
  { width: 1440, height: 900 }, { width: 1280, height: 800 },
  { width: 768, height: 1024 }, { width: 390, height: 844 }, { width: 360, height: 800 },
]

for (const theme of ['light', 'dark']) {
  for (const viewport of viewports) {
    test(`composer geometry ${viewport.width}x${viewport.height} ${theme}`, async ({ page }, info) => {
      test.skip(info.project.name !== 'desktop', 'The full viewport matrix runs once; mobile interactions also run with touch emulation.')
      await page.setViewportSize(viewport)
      await seedChat(page, savedChat(20), theme)
      await page.goto('/')
      await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      const geometry = await page.evaluate(() => {
        const box = (selector: string) => {
          const rect = document.querySelector(selector)!.getBoundingClientRect()
          return { x: rect.x, y: rect.y, width: rect.width, height: rect.height, centerX: rect.x + rect.width / 2, centerY: rect.y + rect.height / 2 }
        }
        return {
          main: box('.chat-main'), rail: box('.chat-rail'), sidebar: box('#chat-sidebar [data-slot="container"]'),
          timeline: box('.chat-timeline'), composer: box('.chat-composer'), textarea: box('.composer-input'),
          controls: ['.composer-attachment', '.composer-model', '.composer-submit'].map(box),
          note: box('.composer-note'), overflow: document.documentElement.scrollWidth > innerWidth,
        }
      })
      expect(geometry.overflow).toBe(false)
      expect(geometry.composer.width).toBeCloseTo(geometry.timeline.width, 0)
      expect(geometry.composer.x).toBeCloseTo(geometry.timeline.x, 0)
      expect(geometry.composer.centerX).toBeCloseTo(geometry.main.centerX, 0)
      expect(geometry.composer.height).toBe(viewport.width > 640 ? 70 : 60)
      expect(geometry.textarea.centerY).toBeCloseTo(geometry.composer.centerY, 0)
      expect(geometry.note.y + geometry.note.height).toBeLessThan(geometry.composer.y)
      for (const control of geometry.controls) {
        expect(control.centerY).toBeCloseTo(geometry.composer.centerY, 0)
        expect(control.x).toBeGreaterThan(geometry.composer.x)
        expect(control.x + control.width).toBeLessThan(geometry.composer.x + geometry.composer.width)
        expect(control.height).toBeGreaterThanOrEqual(44)
      }
      const send = geometry.controls[2]!
      expect(send.width).toBe(send.height)
      if (viewport.width >= 1024) {
        const railWidth = Math.min(68, Math.max(56, viewport.width * 68 / 1920))
        const sidebarWidth = Math.min(376, Math.max(272, viewport.width * 376 / 1920))
        expect(geometry.rail.width).toBeCloseTo(railWidth, 0)
        expect(geometry.rail.height).toBe(viewport.height)
        expect(geometry.sidebar.width).toBeCloseTo(sidebarWidth, 0)
        expect(geometry.main.x).toBeCloseTo(railWidth + sidebarWidth, 0)
        expect(geometry.main.width).toBeCloseTo(viewport.width - railWidth - sidebarWidth, 0)
        if (viewport.width >= 1701) expect(geometry.composer.width).toBeCloseTo(viewport.width * 1000 / 1920, 0)
        const scrollTop = await page.locator('.chat-scroll').evaluate(element => element.scrollTop)
        await page.locator('#chat-sidebar [data-slot="body"]').evaluate(element => { element.scrollTop = element.scrollHeight })
        expect(await page.locator('.chat-scroll').evaluate(element => element.scrollTop)).toBe(scrollTop)
      }
      else {
        await expect(page.locator('.chat-rail')).not.toBeVisible()
        expect(geometry.main.x).toBe(0)
        expect(geometry.main.width).toBe(viewport.width)
        await page.getByRole('button', { name: 'Sidebar öffnen', exact: true }).click()
        await expect(page.getByRole('navigation', { name: 'Gespräche' })).toBeVisible()
        await page.getByRole('button', { name: 'Gesprächsliste schließen', exact: true }).click()
        await expect(page.getByRole('textbox', { name: 'Nachricht', exact: true })).toBeInViewport()
      }
      // Enter keyboard modality after the drawer's pointer interaction.
      await page.keyboard.press('Tab')
      await page.getByRole('button', { name: 'Modell im Eingabefeld auswählen', exact: true }).focus()
      await expect(page.locator('.composer-model')).toBeFocused()
      expect(await page.locator('.composer-model').evaluate(element => getComputedStyle(element).outlineStyle)).toBe('solid')
      await info.attach('composer-geometry', { body: JSON.stringify(geometry, null, 2), contentType: 'application/json' })
    })
  }
}

test('autosizing scrolls only the textarea at its limit and returns to one line', async ({ page }) => {
  await seedChat(page, savedChat())
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const composer = page.locator('.chat-composer')
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  const original = await composer.boundingBox()
  await input.fill('Zeile eins\nZeile zwei\nZeile drei')
  expect((await composer.boundingBox())!.height).toBeGreaterThan(original!.height)
  await input.fill(Array.from({ length: 40 }, (_, index) => `Synthetische Zeile ${index}`).join('\n'))
  const expanded = await composer.boundingBox()
  expect(expanded!.height).toBeLessThan(240)
  expect(await input.evaluate(element => element.scrollHeight > element.clientHeight && getComputedStyle(element).overflowY === 'auto')).toBe(true)
  for (const selector of ['.composer-attachment', '.composer-model', '.composer-submit']) {
    const control = await page.locator(selector).boundingBox()
    expect(control!.y + control!.height / 2).toBeCloseTo(expanded!.y + expanded!.height / 2, 0)
  }
  await input.fill('')
  await expect.poll(async () => (await composer.boundingBox())!.height).toBe(original!.height)
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeDisabled()
})

test('an empty chat keeps a growing draft visible above the visual keyboard viewport', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 })
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  const draft = Array.from({ length: 20 }, (_, index) => `Beispielzeile ${index}`).join('\n')
  await input.fill(draft)
  for (const height of [360, 250]) {
    await page.evaluate(value => {
      const viewport = window.visualViewport!
      Object.defineProperty(viewport, 'height', { configurable: true, value })
      Object.defineProperty(viewport, 'offsetTop', { configurable: true, value: 20 })
      viewport.dispatchEvent(new Event('resize'))
    }, height)
    await expect(input).toBeFocused()
    await expect(input).toHaveValue(draft)
    await expect(page.locator('.empty-chat')).not.toBeVisible()
    const composer = await page.locator('.chat-composer').boundingBox()
    expect(composer!.y).toBeGreaterThanOrEqual(20)
    expect(composer!.y + composer!.height).toBeLessThanOrEqual(height + 20)
    await expect(page.locator('.composer-model')).toBeInViewport()
    await expect(page.locator('.composer-submit')).toBeInViewport()
    expect(await page.evaluate(() => scrollX === 0 && scrollY === 0 && document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
})
