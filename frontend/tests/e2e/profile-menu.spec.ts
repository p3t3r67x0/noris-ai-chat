import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { savedChat, seedChat } from './chat-fixtures'
import { returnToChat } from './settings-helpers'

async function openProfile(page: Page) {
  if ((page.viewportSize()?.width ?? 1024) < 1024 && !await page.locator('.settings-main').isVisible()) {
    await page.getByRole('button', { name: 'Sidebar öffnen', exact: true }).click()
  }
  const trigger = page.locator('.profile-trigger:visible')
  await trigger.click()
  await expect(page.locator('.profile-menu:not(.profile-help-menu)')).toBeVisible()
  await expect(trigger).toHaveAttribute('aria-expanded', 'true')
  expect(await trigger.evaluate(element => getComputedStyle(element).pointerEvents)).toBe('auto')
  return trigger
}

test('profile actions retain the chat draft, restore focus and dismiss on click or Escape', async ({ page }) => {
  await seedChat(page, savedChat())
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const composer = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await composer.fill('Synthetischer Entwurf bleibt erhalten')
  const trigger = await openProfile(page)
  const menu = page.locator('.profile-menu:not(.profile-help-menu)')
  await expect(menu).toContainText('Noris AI')
  await expect(menu).toContainText('Lokale Demo')
  await expect(menu.getByRole('menuitem')).toHaveCount(2)
  await expect(menu.getByText('Abmelden', { exact: true })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await expect(menu).toBeHidden()
  await expect(trigger).toBeFocused()
  await trigger.click()
  await trigger.click()
  await expect(menu).toBeHidden()
  await trigger.click()
  await page.mouse.click(page.viewportSize()!.width - 12, 20)
  await expect(menu).toBeHidden()
  await expect(trigger).toBeFocused()
  await trigger.click()
  await menu.getByRole('menuitem', { name: 'Einstellungen', exact: true }).click()
  await expect(page).toHaveURL(/\/settings\/general$/)
  await expect(page.getByRole('heading', { name: 'Allgemein', exact: true })).toBeFocused()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await returnToChat(page)
  await expect(composer).toHaveValue('Synthetischer Entwurf bleibt erhalten')
})

test('keyboard activation, arrows, Tab and Shift+Tab return to the profile trigger', async ({ page }) => {
  await page.goto('/settings/general')
  // The SSR shell is inert until hydration; focus()/keyboard.press() do not
  // wait for it to become interactive like a pointer click does.
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const trigger = page.locator('.profile-trigger:visible')
  const menu = page.locator('.profile-menu:not(.profile-help-menu)')
  for (const key of ['Enter', 'Space']) {
    await trigger.focus()
    await page.keyboard.press(key)
    await expect(menu).toBeVisible()
    await expect(menu.getByRole('menuitem', { name: 'Einstellungen', exact: true })).toBeFocused()
    await page.keyboard.press('ArrowDown')
    await expect(menu.getByRole('menuitem', { name: 'Hilfe', exact: true })).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(trigger).toBeFocused()
  }
  for (const key of ['Tab', 'Shift+Tab']) {
    await trigger.press('Enter')
    await page.keyboard.press(key)
    await expect(menu).toBeHidden()
    await expect(trigger).toBeFocused()
  }
})

test('desktop help survives the pointer gap and supports both submenu arrow keys', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'Touch uses the same destinations in a nested menu')
  await page.goto('/settings/general')
  await openProfile(page)
  const help = page.getByRole('menuitem', { name: 'Hilfe', exact: true })
  const submenu = page.locator('.profile-help-menu')
  await help.hover()
  await expect(submenu).toBeVisible()
  const parentBox = (await help.boundingBox())!
  const childBox = (await submenu.boundingBox())!
  expect(childBox.x).toBeGreaterThan(parentBox.x + parentBox.width)
  await page.mouse.move((parentBox.x + parentBox.width + childBox.x) / 2, parentBox.y + parentBox.height / 2)
  await page.waitForTimeout(150)
  await expect(submenu).toBeVisible()
  await submenu.getByRole('menuitem', { name: 'Dokumentation', exact: true }).hover()
  await expect(submenu).toBeVisible()
  await page.getByRole('menuitem', { name: 'Einstellungen', exact: true }).hover()
  await expect(submenu).toBeHidden()
  await help.focus()
  await page.keyboard.press('ArrowRight')
  await expect(submenu.getByRole('menuitem', { name: 'Dokumentation', exact: true })).toBeFocused()
  await page.keyboard.press('ArrowLeft')
  await expect(help).toBeFocused()
  await page.keyboard.press('ArrowRight')
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/settings\/keyboard$/)
  await expect(page.getByRole('heading', { name: 'Tastatur', exact: true })).toBeFocused()
})

test('touch help has a back action and opens the existing shortcut route', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile', 'Requires a touch viewport')
  await page.goto('/settings/general')
  await openProfile(page)
  const menu = page.locator('.profile-menu:not(.profile-help-menu)')
  await menu.getByRole('menuitem', { name: 'Hilfe', exact: true }).tap()
  await expect(menu.getByRole('menuitem', { name: 'Zurück', exact: true })).toBeFocused()
  await expect(page.locator('.profile-help-menu')).toHaveCount(0)
  await menu.getByRole('menuitem', { name: 'Zurück', exact: true }).tap()
  await expect(menu.getByRole('menuitem', { name: 'Einstellungen', exact: true })).toBeFocused()
  await menu.getByRole('menuitem', { name: 'Hilfe', exact: true }).tap()
  await menu.getByRole('menuitem', { name: 'Tastaturkürzel', exact: true }).tap()
  await expect(page).toHaveURL(/\/settings\/keyboard$/)
  await expect(page.getByRole('heading', { name: 'Tastatur', exact: true })).toBeFocused()
})

test('submenu flips left and both menus stay within a short viewport', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'Desktop collision behavior')
  await page.setViewportSize({ width: 768, height: 500 })
  await page.goto('/settings/general')
  await page.locator('.profile-trigger:visible').evaluate(element => {
    Object.assign((element as HTMLElement).style, { position: 'fixed', right: '8px', bottom: '8px', zIndex: '30' })
  })
  const trigger = await openProfile(page)
  await page.getByRole('menuitem', { name: 'Hilfe', exact: true }).hover()
  const submenu = page.locator('.profile-help-menu')
  await expect(submenu).toBeVisible()
  await expect(submenu).toHaveAttribute('data-side', 'left')
  for (const menu of [page.locator('.profile-menu:not(.profile-help-menu)'), submenu]) {
    const box = (await menu.boundingBox())!
    expect(box.x).toBeGreaterThanOrEqual(0)
    expect(box.y).toBeGreaterThanOrEqual(0)
    expect(box.x + box.width).toBeLessThanOrEqual(768)
    expect(box.y + box.height).toBeLessThanOrEqual(500)
  }
  await submenu.getByRole('menuitem').first().focus()
  await page.keyboard.press('Escape')
  await page.keyboard.press('Escape')
  await expect(trigger).toBeFocused()
})

for (const theme of ['light', 'dark']) {
  test(`synthetic profile menu visual baseline in ${theme}`, async ({ page }, info) => {
    if (info.project.name === 'desktop') await page.setViewportSize({ width: 1920, height: 975 })
    await seedChat(page, savedChat(0), theme)
    await page.goto('/settings/general')
    await expect(page.locator('html')).toHaveClass(theme === 'dark' ? /dark/ : /light/)
    const trigger = await openProfile(page)
    await page.getByRole('menuitem', { name: 'Hilfe', exact: true }).click()
    const menu = page.locator('.profile-menu:not(.profile-help-menu)')
    if (info.project.name === 'desktop') {
      const submenu = page.locator('.profile-help-menu')
      await expect(submenu).toBeVisible()
      // Visible menus can still be scaling in; measure their final geometry.
      await expect.poll(async () => (await menu.boundingBox())?.width).toBeCloseTo(298, 0)
      await expect.poll(async () => (await submenu.boundingBox())?.width).toBeCloseTo(314, 0)
      const box = (await menu.boundingBox())!
      expect(box.y + box.height).toBeLessThan((await trigger.boundingBox())!.y)
    }
    else await expect(menu.getByRole('menuitem', { name: 'Zurück', exact: true })).toBeVisible()
    await expect(page).toHaveScreenshot(`profile-menu-${theme}.png`, { animations: 'disabled', caret: 'hide' })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
