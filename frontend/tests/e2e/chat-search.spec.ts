import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { savedChat, seedChat } from './chat-fixtures'

function contrast(foreground: string, background: string): number {
  const luminance = (color: string) => {
    const channels = color.match(/[\d.]+/g)!.slice(0, 3).map(value => Number(value) / 255).map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
    return channels[0]! * 0.2126 + channels[1]! * 0.7152 + channels[2]! * 0.0722
  }
  const a = luminance(foreground), b = luminance(background)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

async function start(page: Page, theme = 'light', count = 6) {
  const snapshot = savedChat()
  snapshot.conversations.conversations = Object.fromEntries(Object.entries(snapshot.conversations.conversations).slice(0, count))
  // Keep the sidebar's relative date group stable without freezing Date.now:
  // Vue's event timestamp guards need time to advance for bubbled Tab events.
  const activity = Date.now() - 2 * 24 * 60 * 60 * 1000
  Object.values(snapshot.conversations.conversations).forEach((conversation, index) => {
    conversation.createdAt = conversation.updatedAt = new Date(activity - index).toISOString()
  })
  Object.values(snapshot.messages).forEach(message => { message.createdAt = new Date(activity).toISOString() })
  snapshot.drafts.main = 'Synthetischer Entwurf bleibt erhalten'
  await seedChat(page, snapshot, theme)
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const composer = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await composer.focus()
  await page.keyboard.press('Control+k')
  const dialog = page.getByRole('dialog', { name: 'Chats suchen', exact: true })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('combobox', { name: 'Chats suchen' })).toBeFocused()
  return dialog
}

test('focus, shortcuts, dismissal, reset and a trapped Tab sequence', async ({ page }) => {
  const dialog = await start(page)
  await expect(dialog).toHaveAttribute('aria-modal', 'true')
  await expect(dialog.getByRole('listbox', { name: 'Letzte Chats' })).toHaveAttribute('id', 'chat-search-listbox')
  const input = dialog.getByPlaceholder('Suchen...')
  await expect(dialog.getByRole('heading', { name: 'Chats suchen' })).not.toBeVisible()
  await page.keyboard.press('Tab')
  await expect(dialog.getByRole('button', { name: 'Suche schließen' })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(input).toBeFocused()
  await page.keyboard.press('Shift+Tab')
  await expect(dialog.getByRole('button', { name: 'Suche schließen' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Nachricht', exact: true })).toBeFocused()
  await page.keyboard.press('Meta+k')
  await expect(input).toBeFocused()
  await input.fill('Gedanken')
  await dialog.getByRole('button', { name: 'Suche schließen' }).click()
  await page.keyboard.press('Control+k')
  await expect(input).toHaveValue('')
  await page.mouse.click(2, 2)
  await expect(dialog).not.toBeVisible()
  const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  const trigger = page.locator('.sidebar-heading, .sidebar-primary-actions').getByRole('button', { name: /^(Chat-Suche öffnen|Chats suchen)$/ }).filter({ visible: true })
  await trigger.click()
  await expect(input).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await expect(page.locator('[role="dialog"][data-state="closed"]').filter({ has: page.locator('.sidebar-primary-actions') })).not.toBeVisible()
  if (await trigger.isVisible()) await expect(trigger).toBeFocused()
  else await expect(page.getByRole('textbox', { name: 'Nachricht', exact: true })).toBeFocused()
})

test('search retains the existing interface language setting', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('noris-ai:language', 'en'))
  await seedChat(page, savedChat())
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await page.keyboard.press('Control+k')
  const dialog = page.getByRole('dialog', { name: 'Search chats', exact: true })
  await expect(dialog.getByRole('combobox', { name: 'Search chats' })).toBeFocused()
  await expect(dialog.getByRole('listbox', { name: 'Recent chats' })).toBeVisible()
  await dialog.getByPlaceholder('Search...').fill('zzzzkeintreffer')
  await expect(dialog.getByText('No chats found', { exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: 'Close search' }).click()
  await expect(dialog).not.toBeVisible()
})

test('mouse and keyboard share a quiet selection, Enter opens the chat and drafts survive', async ({ page }) => {
  const dialog = await start(page)
  const input = dialog.getByPlaceholder('Suchen...')
  const options = dialog.getByRole('option')
  await input.press('ArrowDown')
  const current = await input.getAttribute('aria-activedescendant')
  await input.press('ArrowDown')
  expect(await input.getAttribute('aria-activedescendant')).not.toBe(current)
  await input.press('ArrowUp')
  await expect(input).toHaveAttribute('aria-activedescendant', current!)
  await options.nth(3).hover()
  await expect(options.nth(3)).toHaveAttribute('data-highlighted', '')
  await input.press('ArrowDown')
  await expect(options.nth(4)).toHaveAttribute('data-highlighted', '')
  await input.press('Enter')
  await expect(dialog).not.toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Nachricht', exact: true })).toHaveValue('')
  await page.keyboard.press('Control+k')
  await page.getByRole('option', { name: 'Unser Gespräch', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Nachricht', exact: true })).toHaveValue('Synthetischer Entwurf bleibt erhalten')
  await expect(page.locator('.chat-timeline')).toContainText('Ein guter Anfang')
})

test('long untrusted titles remain accessible and ellipsize without overflow', async ({ page }) => {
  const snapshot = savedChat()
  const title = ('<img src=x onerror=alert(1)> ' + 'Synthetischer sehr langer Chat-Titel '.repeat(10)).slice(0, 120)
  snapshot.conversations.conversations.main!.title = title
  await seedChat(page, snapshot)
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await page.keyboard.press('Control+k')
  const option = page.getByRole('option', { name: title, exact: true })
  await expect(option).toBeVisible()
  await expect(option.locator('[title]')).toHaveAttribute('title', title)
  expect(await option.locator('.chat-search-row-title').evaluate(el => el.scrollWidth > el.clientWidth && getComputedStyle(el).textOverflow === 'ellipsis')).toBe(true)
  await expect(option.locator('img')).toHaveCount(0)
  expect(await page.locator('.chat-search-viewport').evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
})

for (const theme of ['light', 'dark']) {
  for (const scene of ['recent', 'matches', 'empty', 'keyboard']) {
    test(`synthetic search ${scene} ${theme}`, async ({ page }, testInfo) => {
      await page.setViewportSize(testInfo.project.name === 'desktop' ? { width: 1920, height: 975 } : { width: 390, height: 844 })
      const dialog = await start(page, theme)
      const input = dialog.getByPlaceholder('Suchen...')
      const before = await dialog.boundingBox()
      if (scene === 'matches') {
        await input.fill('Gespräch')
        await expect(dialog.getByRole('option')).toHaveCount(1)
      }
      if (scene === 'empty') {
        await input.fill('zzzzkeintreffer')
        await expect(dialog.getByText('Keine Chats gefunden')).toBeVisible()
      }
      if (scene === 'keyboard') {
        await input.press('ArrowDown'); await input.press('ArrowDown')
        await expect(dialog.locator('[data-highlighted]')).toHaveCount(1)
      }
      expect((await dialog.boundingBox())!.height).toBe(before!.height)
      await expect(page).toHaveScreenshot(`chat-search-${scene}-${theme}.png`, { animations: 'disabled', caret: 'hide' })
    })
  }
}

for (const theme of ['light', 'dark']) {
  for (const viewport of [{ width: 1920, height: 975 }, { width: 1701, height: 863 }, { width: 1440, height: 900 }, { width: 1280, height: 800 }, { width: 768, height: 1024 }, { width: 390, height: 844 }, { width: 360, height: 800 }]) {
    test(`search geometry ${viewport.width}x${viewport.height} ${theme}`, async ({ page }) => {
      await page.setViewportSize(viewport)
      const dialog = await start(page, theme, 45)
      const box = (await dialog.boundingBox())!
      expect(box.width).toBeCloseTo(Math.min(830, viewport.width - 32), 0)
      expect(box.height).toBe(530)
      expect(box.x + box.width / 2).toBeCloseTo(viewport.width / 2, 0)
      await expect(dialog.getByPlaceholder('Suchen...')).toBeInViewport()
      await expect(dialog.getByRole('button', { name: 'Suche schließen' })).toBeInViewport()
      const close = (await dialog.getByRole('button', { name: 'Suche schließen' }).boundingBox())!
      expect(close.width).toBeGreaterThanOrEqual(44)
      expect(close.height).toBeGreaterThanOrEqual(44)
      const colors = await dialog.evaluate((element) => ({
        background: getComputedStyle(element).backgroundColor,
        primary: getComputedStyle(element.querySelector('.chat-search-row')!).color,
        secondary: getComputedStyle(element.querySelector('.chat-search-label')!).color,
      }))
      expect(contrast(colors.primary, colors.background)).toBeGreaterThanOrEqual(4.5)
      expect(contrast(colors.secondary, colors.background)).toBeGreaterThanOrEqual(4.5)
      expect(await dialog.locator('.chat-search-row').first().evaluate(el => el.getBoundingClientRect().height)).toBe(56)
      await dialog.getByRole('option').last().scrollIntoViewIfNeeded()
      await expect(dialog.getByPlaceholder('Suchen...')).toBeInViewport()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      await page.setViewportSize({ width: viewport.width, height: 320 })
      await expect(dialog.getByPlaceholder('Suchen...')).toBeInViewport()
      await expect(dialog.getByRole('button', { name: 'Suche schließen' })).toBeInViewport()
      expect((await dialog.boundingBox())!.height).toBeLessThanOrEqual(288)
    })
  }
}
