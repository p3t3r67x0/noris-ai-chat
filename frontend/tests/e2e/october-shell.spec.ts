import { expect, test, type Page } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { savedChat, seedChat } from './chat-fixtures'

const viewports = [[1701, 863], [1440, 900], [1280, 800], [1024, 768], [768, 1024], [390, 844]] as const
const selectors = {
  rail: '.chat-rail', sidebar: '.conversation-sidebar', header: '.sidebar-heading',
  newChat: '.sidebar-new-chat', recents: '.sidebar-section', row: '.conversation-row',
  composer: '.chat-composer', textarea: '.composer-input', plus: '.composer-attachment',
  model: '.composer-model', microphone: '.composer-microphone', submit: '.composer-submit',
  greeting: '.empty-chat h1', main: '.chat-main',
}

async function geometry(page: Page) {
  return page.evaluate(selectors => Object.fromEntries(Object.entries(selectors).map(([name, selector]) => {
    const element = [...document.querySelectorAll<HTMLElement>(selector)].find(element => element.getClientRects().length)
    return [name, element ? element.getBoundingClientRect().toJSON() as { x: number, y: number, width: number, height: number, bottom: number } : null]
  })), selectors)
}

for (const theme of ['light', 'dark']) {
  for (const [width, height] of viewports) {
    test(`October shell ${width}x${height} ${theme}`, async ({ page }, info) => {
      test.skip(info.project.name !== 'desktop', 'This matrix defines its own viewports; the mobile project covers touch interactions separately.')
      await page.setViewportSize({ width, height })
      const snapshot = savedChat(0)
      snapshot.conversations.activeConversationId = null
      await seedChat(page, snapshot, theme)
      await page.goto('/')
      await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      await page.evaluate(() => document.fonts.ready)
      const metrics = await geometry(page)
      expect(metrics.composer!.width).toBe(Math.min(888, width - (width >= 1024 ? 340 : 0) - (width > 640 ? 48 : 24)))
      expect(metrics.composer!.x + metrics.composer!.width / 2).toBeCloseTo(metrics.main!.x + metrics.main!.width / 2, 0)
      expect(metrics.greeting!.bottom).toBeLessThan(metrics.composer!.y)
      expect(metrics.composer!.bottom).toBeLessThan(height * 0.55)
      if (width >= 1024) {
        expect(metrics.rail!.width).toBe(52)
        expect(metrics.sidebar!.width).toBe(288)
        expect(metrics.main!.x).toBe(340)
        expect(metrics.composer!.height).toBe(62)
        // 44 px keeps the reference's compact rhythm and a full touch target.
        expect(metrics.row!.height).toBe(44)
      }
      for (const key of ['plus', 'microphone', 'submit']) {
        expect(metrics[key]!.width).toBeGreaterThanOrEqual(44)
        expect(metrics[key]!.height).toBeGreaterThanOrEqual(44)
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      const expectations = width >= 1024 ? [
        { name: 'rail', dimension: 'width', expected: 52, certainty: 'user-stated markup target; original HTML unavailable' },
        { name: 'sidebar', dimension: 'width', expected: 288, certainty: 'derived from user-stated markup targets' },
        { name: 'main', dimension: 'x', expected: 340, certainty: 'user-stated markup target; original HTML unavailable' },
        { name: 'composer', dimension: 'width', expected: Math.min(888, width - 388), certainty: 'visual estimate / responsive Noris rule' },
        { name: 'composer', dimension: 'height', expected: 62, certainty: 'visual estimate' },
        { name: 'row', dimension: 'height', expected: 42.5, certainty: 'visual estimate; 44 px accessibility choice' },
      ] : []
      const comparisons = expectations.map(item => {
        const actual = metrics[item.name]![item.dimension as 'width' | 'height' | 'x']
        return { ...item, actual, absoluteDeviationPx: Math.abs(actual - item.expected), relativeDeviation: Math.abs(actual - item.expected) / item.expected }
      })
      const evidence = { viewport: { width, height, deviceScaleFactor: 1 }, theme, metrics, comparisons }
      const root = resolve('../docs/ui-reference/october-2026')
      await mkdir(root, { recursive: true })
      await writeFile(resolve(root, `geometry-${width}-${theme}.json`), JSON.stringify(evidence, null, 2) + '\n')
      await info.attach('geometry', { body: JSON.stringify(evidence, null, 2), contentType: 'application/json' })
      await expect(page).toHaveScreenshot(`october-${width}-${theme}-empty.png`, { animations: 'disabled' })

      const input = page.locator('.composer-input')
      await input.focus()
      await input.evaluate(element => { element.dataset.retained = 'original' })
      const bottom = (await page.locator('.chat-composer').boundingBox())!
      for (const lines of [2, 5, 40]) {
        await input.fill(Array.from({ length: lines }, (_, index) => `Synthetische Zeile ${index + 1}`).join('\n'))
        await expect(page.locator('.composer-container')).toHaveAttribute('data-layout', lines === 40 ? 'maximized' : 'expanded')
        const grown = (await page.locator('.chat-composer').boundingBox())!
        expect(grown.y + grown.height).toBeCloseTo(bottom.y + bottom.height, 0)
        await expect(input).toBeFocused()
        await expect(input).toHaveAttribute('data-retained', 'original')
      }
      await input.fill('Eine Zeile')
      await expect(page.locator('.composer-container')).toHaveAttribute('data-layout', 'compact')
      await expect.poll(async () => (await page.locator('.chat-composer').boundingBox())!.height).toBe(bottom.height)

      if (width >= 1024) {
        const recent = page.getByRole('button', { name: 'Letzte', exact: true })
        await recent.click()
        await expect(recent).toHaveAttribute('aria-expanded', 'false')
        await expect(page.locator('.conversation-row').first()).toBeHidden()
        await recent.click()
        await expect(page.locator('.conversation-row').first()).toBeVisible()
        const count = await page.locator('.conversation-row').count()
        await page.locator('.sidebar-new-chat').click()
        await expect(input).toBeFocused()
        await expect(input).toHaveValue('Eine Zeile')
        expect(await page.locator('.conversation-row').count()).toBe(count)
        await page.getByRole('button', { name: 'Gesprächsliste schließen', exact: true }).click()
        await expect(input).toHaveValue('Eine Zeile')
        await expect(input).toHaveAttribute('data-retained', 'original')
        await expect.poll(async () => (await page.locator('.chat-main').boundingBox())!.x).toBe(52)
        await input.focus()
        await expect(page).toHaveScreenshot(`october-${width}-${theme}-closed.png`, { animations: 'disabled' })
      }
      else {
        await page.getByRole('button', { name: 'Sidebar öffnen', exact: true }).click()
        await expect(page.getByRole('navigation', { name: 'Gespräche' })).toBeVisible()
        await expect(page).toHaveScreenshot(`october-${width}-${theme}-drawer.png`, { animations: 'disabled' })
        await page.getByRole('button', { name: 'Gesprächsliste schließen', exact: true }).click()
      }
    })
  }

  test(`October interactions and visual states ${theme}`, async ({ page }, info) => {
    test.skip(info.project.name !== 'desktop', 'Desktop interaction matrix runs once.')
    await page.setViewportSize({ width: 1701, height: 863 })
    const snapshot = savedChat(0)
    snapshot.conversations.activeConversationId = null
    await seedChat(page, snapshot, theme)
    await page.clock.setFixedTime(new Date('2026-10-17T12:00:00Z'))
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    const input = page.locator('.composer-input')
    await input.evaluate(element => { element.dataset.retained = 'original' })
    for (const [state, text] of Object.entries({ single: 'Eine synthetische Nachricht', two: 'Erste Zeile\nZweite Zeile', five: 'Eins\nZwei\nDrei\nVier\nFünf', long: 'Lange synthetische Zeile\n'.repeat(40) })) {
      await input.fill(text)
      await expect(page).toHaveScreenshot(`october-${theme}-${state}.png`, { animations: 'disabled' })
    }
    await input.fill('')
    await page.locator('.rail-home').hover()
    await expect(page.locator('.rail-home')).toHaveAttribute('aria-current', 'page')
    await expect(page).toHaveScreenshot(`october-${theme}-rail.png`, { animations: 'disabled' })
    const row = page.locator('.conversation-row').first()
    await row.hover()
    await expect(page).toHaveScreenshot(`october-${theme}-row-hover.png`, { animations: 'disabled' })
    const title = row.locator('button').first()
    await title.focus()
    await title.press('Tab')
    const actions = row.getByRole('button', { name: 'Chat-Aktionen', exact: true })
    await expect(actions).toBeFocused()
    await actions.press('Enter')
    await expect(page.getByRole('menu')).toBeVisible()
    await expect(page).toHaveScreenshot(`october-${theme}-menu.png`, { animations: 'disabled' })
    await page.keyboard.press('Escape')
    await expect(actions).toBeFocused()
    await row.getByRole('button', { name: 'Chat anpinnen', exact: true }).click()
    await expect(page.getByRole('region', { name: 'Fixierte Chats' })).toBeVisible()
    await expect(page).toHaveScreenshot(`october-${theme}-pinned.png`, { animations: 'disabled' })
    await page.locator('.sidebar-new-chat').click()
    await expect(input).toBeFocused()
    await input.fill('/lang')
    await page.clock.install({ time: new Date('2026-10-17T12:00:00Z') })
    await page.clock.pauseAt(new Date(await page.evaluate(() => Date.now()) + 100))
    await input.press('Enter')
    await page.clock.runFor(1500)
    await expect(page.locator('[data-generation-status="streaming"]')).toBeAttached()
    await expect(input).toHaveAttribute('data-retained', 'original')
    await expect(input).toBeFocused()
    await expect(page.locator('.empty-chat')).toHaveCount(0)
    await expect(page).toHaveScreenshot(`october-${theme}-streaming.png`, { animations: 'disabled' })
    await page.getByRole('button', { name: 'Antwort stoppen', exact: true }).click()
    await page.clock.runFor(100)
    await expect(page.locator('[data-generation-status="cancelled"]')).toBeAttached()
    await expect(input).toBeFocused()
    await expect(page).toHaveScreenshot(`october-${theme}-stopped.png`, { animations: 'disabled' })
  })
}
