import { expect, test } from '@playwright/test'
import { captureScene } from './reference-scenes'
import { savedChat, seedChat } from './chat-fixtures'

test.use({ viewport: { width: 1920, height: 975 }, deviceScaleFactor: 1 })
for (const theme of ['light', 'dark']) {
  for (const scene of ['empty', 'active', 'streaming', 'sidebar-open', 'sidebar-closed', 'code', 'long']) {
    test(`reference desktop ${scene} ${theme}`, async ({ page }, testInfo) => { await captureScene(page, testInfo, scene, theme) })
  }
}
test('original reference size with synthetic content', async ({ page }, testInfo) => {
  await captureScene(page, testInfo, 'reference', 'light')
  const rail = await page.locator('.chat-rail').boundingBox()
  const sidebar = await page.locator('#chat-sidebar [data-slot="container"]').boundingBox()
  const composer = await page.locator('.chat-composer').boundingBox()
  const timeline = await page.locator('.chat-timeline').boundingBox()
  expect(rail!.width).toBeCloseTo(68, 0)
  expect(sidebar!.x).toBeCloseTo(68, 0)
  expect(sidebar!.width).toBeCloseTo(376, 0)
  expect(composer!.width).toBeCloseTo(1000, 0)
  expect(composer!.height).toBeCloseTo(70, 0)
  expect(975 - composer!.y - composer!.height).toBeCloseTo(29, 0)
  expect(timeline!.x).toBeCloseTo(composer!.x, 0)
  expect(timeline!.width).toBeCloseTo(composer!.width, 0)
})

for (const theme of ['light', 'dark']) {
  for (const viewport of [{ width: 1701, height: 863 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 1280, height: 800 }, { width: 768, height: 1024 }, { width: 390, height: 844 }, { width: 360, height: 800 }]) {
    test(`bounded layout ${viewport.width}x${viewport.height} ${theme}`, async ({ page }) => {
      await page.setViewportSize(viewport)
      await seedChat(page, savedChat(1), theme)
      await page.goto('/')
      await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      await expect(page.getByRole('textbox', { name: 'Nachricht', exact: true })).toBeInViewport()
      await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeInViewport()
      const boxes = await page.locator('.chat-composer').boundingBox()
      expect(boxes!.x).toBeGreaterThanOrEqual(0)
      expect(boxes!.x + boxes!.width).toBeLessThanOrEqual(viewport.width)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth && scrollY === 0)).toBe(true)
    })
  }
}
