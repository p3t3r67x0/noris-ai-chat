import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { savedChat } from './chat-fixtures'
import { CHAT_STORAGE_KEY } from '../../app/lib/chat/persistence'

async function sidebar(page: Page) {
  const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  await expect(page.getByRole('navigation', { name: 'Gespräche' })).toBeVisible()
}
async function send(page: Page, text: string) {
  const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
  if ((page.viewportSize()?.width ?? 1920) < 1024 && await toggle.getAttribute('aria-expanded') === 'true') await page.getByRole('button', { name: 'Gesprächsliste schließen', exact: true }).click()
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.fill(text); await input.press('Enter')
}
async function pause(page: Page) {
  await page.clock.install()
  await page.clock.pauseAt(new Date(await page.evaluate(() => Date.now()) + 100))
}
test.beforeEach(async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true', { timeout: 15_000 })
})

test('mock fallback updates asynchronously, retains row geometry and survives switching and reload', async ({ page }, info) => {
  let requests = 0
  page.on('request', request => { if (request.url().includes('/api/v1/llm/conversation-title')) requests++ })
  await sidebar(page)
  await pause(page)
  await send(page, 'Welche Vorteile bietet Rust gegenüber C++?')
  await sidebar(page)
  const row = page.getByRole('navigation', { name: 'Gespräche' }).locator('.conversation-row').first()
  await expect(row.locator('button').first()).toHaveAttribute('title', 'Neuer Chat')
  const before = await row.boundingBox()
  await page.clock.runFor(800)
  await expect(row.locator('button').first()).toHaveAttribute('title', 'Rust vs. C++')
  await expect(page.locator('[data-generation-status="streaming"]')).toBeAttached()
  const after = await row.boundingBox()
  expect(after!.width).toBeCloseTo(before!.width, 0)
  expect(after!.height).toBeCloseTo(before!.height, 0)
  await page.screenshot({ path: info.outputPath('generated-title.png'), animations: 'disabled' })
  await page.clock.runFor(4000)
  const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
  if (await toggle.getAttribute('aria-expanded') === 'true') await page.getByRole('button', { name: 'Gesprächsliste schließen', exact: true }).click()
  await page.locator('.chat-header').getByRole('button', { name: 'Neuer Chat', exact: true }).click()
  await send(page, 'Why does Docker DNS fail?')
  await page.clock.runFor(4000)
  await sidebar(page)
  const navigation = page.getByRole('navigation', { name: 'Gespräche' })
  await expect(navigation.getByRole('button', { name: 'Docker DNS troubleshooting', exact: true })).toBeVisible()
  await navigation.getByRole('button', { name: 'Rust vs. C++', exact: true }).click()
  await page.clock.resume()
  await page.reload()
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await sidebar(page)
  await expect(navigation.getByRole('button', { name: 'Rust vs. C++', exact: true })).toHaveAttribute('aria-current', 'page')
  const sources = await page.evaluate(key => Object.values(JSON.parse(localStorage.getItem(key)!).conversations.conversations).map(item => (item as { titleSource: string }).titleSource), CHAT_STORAGE_KEY)
  expect(sources).toEqual(['generated', 'generated'])
  expect(requests).toBe(0)
})

test('manual rename wins while the synthetic title is pending', async ({ page }) => {
  await pause(page)
  await send(page, 'Warum funktioniert Docker DNS nicht?')
  await page.clock.runFor(500)
  await sidebar(page)
  await page.getByRole('button', { name: 'Aktionen für Neuer Chat' }).click()
  await page.getByRole('menuitem', { name: 'Umbenennen' }).click()
  await page.getByRole('textbox', { name: 'Chat-Titel' }).fill('Meine DNS-Notizen')
  await page.getByRole('textbox', { name: 'Chat-Titel' }).press('Enter')
  await page.clock.runFor(4000)
  await sidebar(page)
  await expect(page.getByRole('navigation', { name: 'Gespräche' }).getByRole('button', { name: 'Meine DNS-Notizen', exact: true })).toBeVisible()
  const sources = await page.evaluate(key => Object.values(JSON.parse(localStorage.getItem(key)!).conversations.conversations).map(item => (item as { titleSource: string }).titleSource), CHAT_STORAGE_KEY)
  expect(sources).toEqual(['manual'])
})

test('deletion while generating never revives a conversation', async ({ page }) => {
  await pause(page)
  await send(page, 'Warum funktioniert Docker DNS nicht?')
  await page.clock.runFor(500)
  await sidebar(page)
  await page.getByRole('button', { name: 'Aktionen für Neuer Chat' }).click()
  await page.getByRole('menuitem', { name: 'Löschen', exact: true }).click()
  await page.getByRole('dialog', { name: 'Chat löschen?' }).getByRole('button', { name: 'Chat löschen', exact: true }).click()
  await page.clock.runFor(4000)
  await sidebar(page)
  await expect(page.locator('.conversation-row')).toHaveCount(0)
  expect(await page.evaluate(key => Object.keys(JSON.parse(localStorage.getItem(key)!).conversations.conversations), CHAT_STORAGE_KEY)).toEqual([])
})

test('long generated titles use the existing single-line ellipsis without widening the sidebar', async ({ page }) => {
  const snapshot = savedChat()
  const conversation = Object.values(snapshot.conversations.conversations)[0]!
  conversation.title = 'W'.repeat(50)
  conversation.titleSource = 'generated'
  await page.addInitScript(({ key, value }) => localStorage.setItem(key, value), { key: CHAT_STORAGE_KEY, value: JSON.stringify(snapshot) })
  await page.reload()
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await sidebar(page)
  const label = page.getByRole('navigation', { name: 'Gespräche' }).locator('.conversation-row > button:first-child span').first()
  const geometry = await label.evaluate(element => ({ nowrap: getComputedStyle(element).whiteSpace, ellipsis: getComputedStyle(element).textOverflow, clipped: element.scrollWidth > element.clientWidth, height: element.getBoundingClientRect().height, lineHeight: parseFloat(getComputedStyle(element).lineHeight) }))
  expect(geometry).toMatchObject({ nowrap: 'nowrap', ellipsis: 'ellipsis', clipped: true })
  expect(geometry.height).toBeLessThanOrEqual(geometry.lineHeight)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
