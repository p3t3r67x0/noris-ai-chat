import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { writeFile } from 'node:fs/promises'
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
  await expect(row.locator('button').first()).toHaveAttribute('title', 'Rust vs. C++')
  await expect(row.locator('span[data-title-source]')).toHaveAttribute('data-title-source', 'fallback')
  const before = await row.boundingBox()
  await page.clock.runFor(800)
  await expect(row.locator('button').first()).toHaveAttribute('title', 'Rust vs. C++')
  await expect(row.locator('span[data-title-source]')).toHaveAttribute('data-title-source', 'generated')
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
  await expect(navigation.getByRole('button', { name: /^Docker DNS(?: Troubleshooting)?$/ })).toBeVisible()
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
  await page.getByRole('button', { name: 'Aktionen für Docker DNS-Probleme' }).click()
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
  await page.getByRole('button', { name: 'Aktionen für Docker DNS-Probleme' }).click()
  await page.getByRole('menuitem', { name: 'Löschen', exact: true }).click()
  await page.getByRole('dialog', { name: 'Chat löschen?' }).getByRole('button', { name: 'Chat löschen', exact: true }).click()
  await page.clock.runFor(4000)
  await sidebar(page)
  await expect(page.locator('.conversation-row')).toHaveCount(0)
  expect(await page.evaluate(key => Object.keys(JSON.parse(localStorage.getItem(key)!).conversations.conversations), CHAT_STORAGE_KEY)).toEqual([])
})

test('long manual titles retain single-line ellipsis and an accessible full name', async ({ page }) => {
  const snapshot = savedChat()
  const conversation = Object.values(snapshot.conversations.conversations)[0]!
  conversation.title = 'Meine vollständigen Notizen zur automatischen Chat-Titelgenerierung'
  conversation.titleSource = 'manual'
  await page.addInitScript(({ key, value }) => localStorage.setItem(key, value), { key: CHAT_STORAGE_KEY, value: JSON.stringify(snapshot) })
  await page.reload()
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await sidebar(page)
  const label = page.getByRole('navigation', { name: 'Gespräche' }).locator('.conversation-row > button:first-child span').first()
  const geometry = await label.evaluate(element => ({ nowrap: getComputedStyle(element).whiteSpace, ellipsis: getComputedStyle(element).textOverflow, clipped: element.scrollWidth > element.clientWidth, height: element.getBoundingClientRect().height, lineHeight: parseFloat(getComputedStyle(element).lineHeight) }))
  expect(geometry).toMatchObject({ nowrap: 'nowrap', ellipsis: 'ellipsis', clipped: true })
  expect(geometry.height).toBeLessThanOrEqual(geometry.lineHeight)
  await expect(label.locator('..')).toHaveAccessibleName(conversation.title)
  await expect(label.locator('..')).toHaveAttribute('title', conversation.title)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

for (const size of [{ width: 1920, height: 975 }, { width: 1440, height: 900 }, { width: 1280, height: 800 }, { width: 390, height: 844 }]) {
  test(`automatic titles fit the actual text area at ${size.width}×${size.height}`, async ({ page }, info) => {
    await page.setViewportSize(size)
    const snapshot = savedChat()
    const examples = ['Automatisierte Chat-Titel Implementierung', 'Fiktive Beispiele sammeln', 'Neutrale Aufgaben planen', 'Synthetische Notizen ordnen', 'Beispielabläufe prüfen', 'Docker DNS Troubleshooting Guide', 'WWWWWWWWWWWWWWWWWWWW WWWWWWWWWWW', 'PostgreSQL vs. MariaDB', 'ÖPNV & Mobilität']
    for (const [index, conversation] of Object.values(snapshot.conversations.conversations).entries()) {
      conversation.title = examples[index % examples.length]!
      conversation.titleSource = 'generated'
    }
    await page.addInitScript(({ key, value }) => localStorage.setItem(key, value), { key: CHAT_STORAGE_KEY, value: JSON.stringify(snapshot) })
    await page.reload()
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    await sidebar(page)
    const rows = page.getByRole('navigation', { name: 'Gespräche' }).locator('.conversation-row')
    await expect(rows.first().locator('button').first()).toHaveText('Automatische Chat-Titel')
    await expect.poll(async () => await rows.evaluateAll(items => items.every((item) => {
      const label = item.querySelector('span[data-title-source]')!
      const range = document.createRange(); range.selectNodeContents(label)
      return range.getBoundingClientRect().width <= label.clientWidth && label.scrollWidth <= label.clientWidth
    }))).toBe(true)
    const geometry = await rows.evaluateAll(items => items.map((item) => {
      const label = item.querySelector('span[data-title-source]')!
      const style = getComputedStyle(label)
      const range = document.createRange(); range.selectNodeContents(label)
      return { title: label.textContent!, height: item.getBoundingClientRect().height, textWidth: range.getBoundingClientRect().width, available: label.clientWidth, nowrap: style.whiteSpace, overflow: style.textOverflow, lineHeight: parseFloat(style.lineHeight), textHeight: label.getBoundingClientRect().height }
    }))
    for (const item of geometry) {
      expect(item.title.length).toBeLessThanOrEqual(40)
      expect(item.title).not.toMatch(/…|\.{2}/)
      expect(item.nowrap).toBe('nowrap')
      expect(item.overflow).toBe('clip')
      expect(item.textWidth).toBeLessThanOrEqual(item.available)
      expect(item.textHeight).toBeLessThanOrEqual(item.lineHeight)
      expect(item.height).toBe(geometry[0]!.height)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
    const evidence = info.outputPath('title-widths.json')
    await writeFile(evidence, JSON.stringify(geometry, null, 2))
    await info.attach('title-widths', { path: evidence, contentType: 'application/json' })
    await page.screenshot({ path: info.outputPath(`concise-titles-${size.width}.png`), animations: 'disabled' })
    await rows.first().getByRole('button', { name: 'Aktionen für Automatische Chat-Titel' }).click()
    await expect(page.getByRole('menuitem', { name: 'Umbenennen' })).toBeVisible()
  })
}

test('the acceptance prompt produces a complete thematic title during streaming', async ({ page }) => {
  await pause(page)
  await send(page, 'Kannst du mir helfen, eine automatische Chat-Titelgenerierung für Noris AI zu implementieren und dabei die bestehende Architektur zu erhalten?')
  await sidebar(page)
  const row = page.getByRole('navigation', { name: 'Gespräche' }).locator('.conversation-row').first()
  await expect(row.locator('button').first()).toHaveText('Automatische Chat-Titel')
  await expect(row.locator('span[data-title-source]')).toHaveAttribute('data-title-source', 'fallback')
  await page.clock.runFor(800)
  await expect(row.locator('span[data-title-source]')).toHaveAttribute('data-title-source', 'generated')
  await expect(page.locator('[data-generation-status="streaming"]')).toBeAttached()
  await page.clock.runFor(4000)
  await page.clock.resume()
  await page.reload()
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await sidebar(page)
  await expect(page.getByRole('navigation', { name: 'Gespräche' }).getByRole('button', { name: 'Automatische Chat-Titel', exact: true })).toBeVisible()
})
