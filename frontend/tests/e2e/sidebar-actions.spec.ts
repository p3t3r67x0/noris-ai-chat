import { expect, test, type Page } from '@playwright/test'
import { savedChat, seedChat } from './chat-fixtures'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const sizes = [[1700, 900], [1440, 900], [768, 1024], [390, 844]] as const
async function sidebar(page: Page) {
  const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  await expect(page.getByRole('navigation', { name: 'Gespräche', exact: true })).toBeVisible()
}
async function centered(page: Page) {
  const geometry = await page.locator('.chat-rail').evaluate(rail => {
    const rect = rail.getBoundingClientRect()
    const axis = rect.left + rect.width / 2
    return { axis, items: Array.from(rail.querySelectorAll('button')).map(button => {
      const rect = button.getBoundingClientRect()
      const icon = button.querySelector('.iconify, .rail-mark, .profile-avatar')!.getBoundingClientRect()
      return { button: rect.left + rect.width / 2, icon: icon.left + icon.width / 2, width: rect.width, height: rect.height }
    }) }
  })
  expect(geometry.items).toHaveLength(4)
  for (const item of geometry.items) {
    expect(Math.abs(item.button - geometry.axis)).toBeLessThanOrEqual(1)
    expect(Math.abs(item.icon - geometry.axis)).toBeLessThanOrEqual(1)
    expect(item.width).toBe(44)
    expect(item.height).toBe(44)
  }
  const centers = geometry.items.map(item => item.icon)
  expect(Math.max(...centers) - Math.min(...centers)).toBeLessThanOrEqual(1)
  return geometry
}

for (const [width, height] of sizes) for (const theme of ['light', 'dark']) {
  test.describe(`${width} ${theme} sidebar`, () => {
    test.use({ viewport: { width, height }, hasTouch: width < 1024, isMobile: width < 1024 })
    test('rail geometry, chat actions, keyboard, menu and visual states', async ({ page }, testInfo) => {
      test.skip(testInfo.project.name !== 'desktop', 'The matrix sets its own desktop/touch viewports.')
      const snapshot = savedChat()
      snapshot.conversations.conversations = Object.fromEntries(Object.entries(snapshot.conversations.conversations).slice(0, 3))
      await seedChat(page, snapshot, theme)
      await page.goto('/')
      await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      await sidebar(page)
      const evidence = resolve('..', 'docs/sidebar/evidence')
      await mkdir(evidence, { recursive: true })
      const screenshot = async (state: string) => {
        const path = resolve(evidence, `after-${width}-${theme}-${state}.png`)
        await page.screenshot({ path, animations: 'disabled' })
        await testInfo.attach(state, { path, contentType: 'image/png' })
      }
      const row = page.locator('.conversation-row[data-conversation-id="main"]:visible')
      const actions = row.getByRole('button', { name: 'Chat-Aktionen', exact: true })
      const pin = row.getByRole('button', { name: 'Chat anpinnen', exact: true })
      const title = row.getByRole('button', { name: 'Unser Gespräch', exact: true })
      await page.mouse.move(width - 10, height - 10)
      await title.blur()
      if (width >= 1024) {
        await expect(actions).toBeHidden()
        await expect(pin).toBeHidden()
        const before = await centered(page)
        await writeFile(resolve(evidence, `after-${width}-${theme}-geometry.json`), JSON.stringify(before, null, 2) + '\n')
        for (const button of await page.locator('.chat-rail button').all()) {
          await button.hover(); await centered(page)
          await button.focus(); await centered(page)
        }
        await page.locator('.chat-rail button').last().click()
        await centered(page)
        await page.keyboard.press('Escape')
        await page.getByRole('button', { name: 'Gesprächsliste schließen' }).click()
        await centered(page)
        await sidebar(page)
        expect((await centered(page)).axis).toBe(before.axis)
        await expect.poll(async () => (await page.locator('.conversation-sidebar').boundingBox())?.width).toBeCloseTo(288, 0)
      }
      else {
        await expect(page.locator('.chat-rail')).toBeHidden()
        for (const button of [actions, pin]) {
          await expect(button).toBeVisible()
          // Wait for the drawer's scale animation; keep only a rounding tolerance.
          await expect.poll(async () => (await button.boundingBox())?.width ?? 0).toBeGreaterThanOrEqual(44 - 0.01)
          await expect.poll(async () => (await button.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44 - 0.01)
        }
      }
      await page.mouse.move(width - 10, height - 10)
      await title.blur()
      await screenshot('normal')
      const rowRect = await row.boundingBox()
      if (width >= 1024) await row.hover()
      await expect(actions).toBeVisible()
      await expect(pin).toBeVisible()
      expect(await row.boundingBox()).toEqual(rowRect)
      await screenshot('hover')
      await title.focus()
      await expect(title).toBeFocused()
      await page.mouse.move(width - 10, height - 10)
      await expect(actions).toBeVisible()
      await title.press('Tab')
      await expect(actions).toBeFocused()
      await actions.press('Enter')
      const menu = page.getByRole('menu')
      await expect(menu).toBeVisible()
      await expect(actions).toHaveAttribute('aria-expanded', 'true')
      await expect(actions).toBeVisible()
      expect(await row.boundingBox()).toEqual(rowRect)
      const menuRect = await menu.boundingBox()
      expect(menuRect!.x).toBeGreaterThanOrEqual(0)
      expect(menuRect!.x + menuRect!.width).toBeLessThanOrEqual(width)
      expect(menuRect!.y + menuRect!.height).toBeLessThanOrEqual(height)
      if (width >= 1024) expect(menuRect!.x).toBeGreaterThanOrEqual(rowRect!.x + rowRect!.width)
      if (width < 1024) {
        for (const item of await menu.getByRole('menuitem').all()) {
          await expect.poll(async () => (await item.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44 - 0.01)
        }
      }
      if (width >= 1024) await centered(page)
      await screenshot('menu')
      await page.keyboard.press('ArrowDown')
      await expect(menu.getByRole('menuitem', { name: 'Chat anpinnen' })).toBeFocused()
      await page.keyboard.press('Escape')
      await expect(menu).toBeHidden()
      await expect(actions).toBeFocused()
      await actions.click(); await expect(menu).toBeVisible()
      await actions.click(); await expect(menu).toBeHidden()
      await actions.click(); await expect(menu).toBeVisible()
      await page.locator('.sidebar-title:visible').click()
      await expect(menu).toBeHidden()
      if (width >= 1024) await row.hover()
      await pin.hover()
      await screenshot('pin-hover')
      await pin.click()
      const pinned = page.getByRole('region', { name: 'Fixierte Chats', exact: true })
      await expect(pinned).toContainText('Unser Gespräch')
      await expect(page.locator('[data-conversation-id="main"]:visible')).toHaveCount(1)
      await expect(page.locator('[data-conversation-id="main"]:visible')).toHaveAttribute('data-active', 'true')
      await expect(page.locator('[data-conversation-id="main"]:visible').getByRole('button', { name: 'Chat-Fixierung lösen' })).toBeFocused()
      await screenshot('pinned')
      if (width < 1024) await screenshot('mobile-sidebar')
      await page.reload(); await sidebar(page)
      await expect(pinned).toContainText('Unser Gespräch')
      const pinnedRow = pinned.locator('[data-conversation-id="main"]:visible')
      if (width >= 1024) await pinnedRow.hover()
      await pinnedRow.getByRole('button', { name: 'Chat-Fixierung lösen' }).click()
      await expect(pinned).toHaveCount(0)
      await expect(page.locator('[data-conversation-id="main"]:visible')).toHaveCount(1)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    })
  })
}
