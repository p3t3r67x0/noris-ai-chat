import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { savedChat, seedChat } from './chat-fixtures'
import { originalCode, overflowMarkdown, strengthTable } from '../fixtures/markdown'

async function expectBoundedMarkdown(page: Page): Promise<void> {
  const violations = await page.evaluate(() => {
    const failures: string[] = []
    const root = document.documentElement
    if (root.scrollWidth > root.clientWidth) failures.push('document')
    const timeline = document.querySelector('.chat-timeline')!.getBoundingClientRect()
    for (const element of document.querySelectorAll('.chat-scroll, .chat-message, .assistant-content, .markdown-content, .markdown-table, table, th, td, .code-block, .code-block[data-wrap="true"] pre')) {
      const rect = element.getBoundingClientRect()
      if (element.scrollWidth > element.clientWidth) failures.push(`${element.tagName}.${element.className}: scrollWidth`)
      if (!element.matches('.chat-scroll') && (rect.left < timeline.left - 1 || rect.right > timeline.right + 1)) failures.push(`${element.tagName}.${element.className}: bounds`)
    }
    // Checking text fragments also catches clipping that element sizes hide.
    for (const cell of document.querySelectorAll('th, td, .code-block[data-wrap="true"] pre')) {
      const bounds = cell.getBoundingClientRect()
      const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT)
      while (walker.nextNode()) {
        const node = walker.currentNode
        if (!node.textContent?.trim()) continue
        const range = document.createRange()
        range.selectNodeContents(node)
        for (const rect of range.getClientRects()) {
          if (rect.left < bounds.left - 1 || rect.right > bounds.right + 1) failures.push(`${cell.tagName}: text fragment`)
        }
      }
    }
    for (const button of document.querySelectorAll('.code-block button')) {
      const rect = button.getBoundingClientRect()
      const caption = button.closest('figcaption')!.getBoundingClientRect()
      if (rect.left < caption.left || rect.right > caption.right || rect.width < 44 || rect.height < 44) failures.push('code control')
    }
    return failures
  })
  expect(violations).toEqual([])
}

for (const viewport of [{ width: 1920, height: 975 }, { width: 1440, height: 900 }, { width: 1280, height: 800 }, { width: 768, height: 1024 }, { width: 390, height: 844 }, { width: 360, height: 800 }]) {
  test(`tables, URLs, code and nested lists wrap at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    const snapshot = savedChat()
    snapshot.messages['assistant-0']!.content = overflowMarkdown
    snapshot.messages['user-0']!.content = 'Prüfe Tabellen und lange Antworten.'
    await seedChat(page, snapshot)
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    await expect(page.locator('.syntax-token').first()).toBeAttached()
    await expect(page.locator('table')).toHaveCount(2)
    await expect(page.locator('td')).toHaveCount(14)
    await expectBoundedMarkdown(page)
    if (viewport.width >= 1024) {
      const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
      await expect(toggle).toHaveAttribute('aria-expanded', 'true')
      await toggle.click()
      await expect(toggle).toHaveAttribute('aria-expanded', 'false')
      await expectBoundedMarkdown(page)
    }
    await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeInViewport()
  })
}

test('code wrapping toggles by keyboard, retains highlighting and copies the original code', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  const snapshot = savedChat()
  snapshot.messages['assistant-0']!.content = `\`\`\`python\n${originalCode}\`\`\``
  await seedChat(page, snapshot)
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const block = page.locator('.code-block')
  const pre = block.locator('pre')
  const toggle = block.getByRole('button', { name: 'Zeilenumbruch umschalten' })
  await expect(block.locator('.syntax-token').first()).toBeAttached()
  await expect(toggle).toHaveAttribute('aria-pressed', 'true')
  expect(await pre.textContent()).toBe(originalCode)
  await expectBoundedMarkdown(page)
  await block.getByRole('button', { name: 'Code kopieren' }).click()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(originalCode)
  await toggle.focus()
  await page.keyboard.press('Enter')
  await expect(toggle).toHaveAttribute('aria-pressed', 'false')
  expect(await pre.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true)
  await expectBoundedMarkdown(page)
  await block.getByRole('button', { name: 'Kopiert' }).click()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(originalCode)
  await toggle.focus()
  await page.keyboard.press('Space')
  await expect(toggle).toHaveAttribute('aria-pressed', 'true')
  expect(await pre.textContent()).toBe(originalCode)
  await expect(block.locator('.syntax-token').first()).toBeAttached()
  await expectBoundedMarkdown(page)
})

test('incomplete streaming tables stay bounded and preserve following and manual reading', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await page.clock.install()
  await page.clock.pauseAt(new Date(await page.evaluate(() => Date.now()) + 100))
  // The existing mock echoes this Markdown prompt through real incremental deltas.
  const row = `| Klarheit | ${'Vollständig lesbare deutsche Beschreibung. '.repeat(8)} | https://example.com/${'pfad'.repeat(50)} | ${'Dateiname'.repeat(50)} | Weitere Angaben |\n`
  const table = `| Stärke | Bedeutung | Link | Datei | Kontext |\n| --- | --- | --- | --- | --- |\n${row.repeat(3)}`
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.fill(`Prüfe diese Tabellen.\n\n${strengthTable}\n\n${table}\n\nEnde der Beispiele.`)
  await input.press('Enter')
  await page.clock.runFor(50)
  const scroll = page.locator('.chat-scroll')
  const startTop = await scroll.evaluate(element => element.scrollTop)
  let sawPartialTable = false
  for (let step = 0; step < 22; step++) {
    await page.clock.runFor(250)
    await expectBoundedMarkdown(page)
    if (await page.locator('.message-assistant table').count()) sawPartialTable = true
  }
  expect(sawPartialTable).toBe(true)
  await expect(page.locator('[data-generation-status]')).toHaveAttribute('data-generation-status', 'streaming')
  expect(await scroll.evaluate(element => element.scrollTop)).toBeGreaterThan(startTop)
  await scroll.evaluate(element => { element.scrollTop -= 200; element.dispatchEvent(new Event('scroll')) })
  const readingTop = await scroll.evaluate(element => element.scrollTop)
  await page.clock.runFor(500)
  expect(await scroll.evaluate(element => element.scrollTop)).toBeCloseTo(readingTop, 0)
  await expectBoundedMarkdown(page)
  await page.getByRole('button', { name: 'Zum Ende scrollen' }).click()
  await page.clock.runFor(10_000)
  await expect(page.locator('[data-generation-status]')).toHaveAttribute('data-generation-status', 'completed')
  expect(await scroll.evaluate(element => element.scrollHeight - element.clientHeight - element.scrollTop)).toBeLessThan(3)
  await expect(page.locator('.message-assistant table')).toHaveCount(3)
  await expectBoundedMarkdown(page)
})

test('Stärke and Bedeutung remain fully visible in desktop and mobile screenshots', async ({ page }, testInfo) => {
  await page.setViewportSize(testInfo.project.name === 'desktop' ? { width: 1920, height: 975 } : { width: 390, height: 844 })
  const snapshot = savedChat()
  snapshot.messages['user-0']!.content = 'Welche Stärken helfen bei einer ausführlichen Antwort?'
  snapshot.messages['assistant-0']!.content = `## Stärken im Überblick\n\n${strengthTable}\n\nAlle Beschreibungen bleiben vollständig lesbar.`
  await seedChat(page, snapshot)
  await page.clock.setFixedTime(new Date('2026-10-09T12:00:00Z'))
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await page.locator('table').scrollIntoViewIfNeeded()
  await expectBoundedMarkdown(page)
  await page.screenshot({ path: testInfo.outputPath('markdown-strengths.png'), animations: 'disabled', caret: 'hide' })
  await expect(page).toHaveScreenshot('markdown-strengths.png', { animations: 'disabled', caret: 'hide' })
})
