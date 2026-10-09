import { expect, test } from '@playwright/test'
import { savedChat, seedChat } from './chat-fixtures'

test('a short send anchors the question and preserves the same focused composer', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.evaluate(element => { element.dataset.instance = 'original' })
  await input.fill('Meine Frage')
  await page.clock.install()
  await page.clock.pauseAt(new Date(await page.evaluate(() => Date.now()) + 100))
  await input.press('Enter')
  await page.clock.runFor(50)
  await expect(input).toBeFocused()
  await expect(input).toHaveAttribute('data-instance', 'original')
  const header = await page.locator('.chat-header').boundingBox()
  const question = await page.locator('.message-user').boundingBox()
  expect(question!.y - header!.y - header!.height).toBeGreaterThanOrEqual(0)
  expect(question!.y - header!.y - header!.height).toBeLessThan(40)
  await page.getByRole('button', { name: 'Antwort stoppen', exact: true }).click()
  await page.clock.runFor(50)
  await expect(input).toBeFocused()
  await expect(page.locator('[data-generation-status]')).toHaveAttribute('data-generation-status', 'cancelled')
})

test('a growing composer and VisualViewport keyboard resizing keep one conversation scroller', async ({ page }) => {
  await seedChat(page, savedChat(3))
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  const original = await page.locator('.chat-composer').boundingBox()
  await input.fill(Array.from({ length: 16 }, (_, index) => `Zeile ${index + 1}: ein weiterer Gedanke`).join('\n'))
  const expanded = await page.locator('.chat-composer').boundingBox()
  expect(expanded!.height).toBeGreaterThan(original!.height)
  expect(expanded!.height).toBeLessThan(240)
  const position = await page.locator('.chat-scroll').evaluate(element => { element.scrollTop = 0; element.dispatchEvent(new Event('scroll')); return element.scrollTop })
  await page.evaluate(() => {
    const viewport = window.visualViewport
    if (!viewport) throw new Error('VisualViewport missing')
    Object.defineProperty(viewport, 'height', { configurable: true, value: 420 })
    viewport.dispatchEvent(new Event('resize'))
  })
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeInViewport()
  const dock = await page.locator('.chat-composer').boundingBox()
  expect(dock!.y + dock!.height).toBeLessThanOrEqual(420)
  expect(await page.locator('.chat-scroll').evaluate(element => element.scrollTop)).toBe(position)
  await expect(input).toHaveValue(/Zeile 16/)
  const outer = await page.evaluate(() => [...document.querySelectorAll('.chat-main, .chat-content, .chat-history')].filter(element => ['auto', 'scroll'].includes(getComputedStyle(element).overflowY)).length)
  expect(outer).toBe(0)
})

test('switching conversations during a stream keeps drafts and independent scroll positions', async ({ page }) => {
  await seedChat(page, savedChat(20))
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.fill('/lang')
  await page.clock.install()
  await page.clock.pauseAt(new Date(await page.evaluate(() => Date.now()) + 100))
  await input.press('Enter')
  await page.clock.runFor(1000)
  await expect(page.locator('[data-generation-status]')).toHaveAttribute('data-generation-status', 'streaming')
  const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  await page.getByRole('navigation', { name: 'Gespräche' }).getByRole('button', { name: 'Gedanken 1', exact: true }).click()
  await input.fill('Entwurf im anderen Chat')
  await expect(page.getByRole('button', { name: 'Antwort läuft in einem anderen Chat' })).toBeVisible()
  await page.getByRole('button', { name: 'Antwort läuft in einem anderen Chat' }).click()
  await expect(input).toHaveValue('')
  await expect(page.locator('.message-assistant').last()).toContainText('Gedanke')
  await page.getByRole('button', { name: 'Antwort stoppen', exact: true }).click()
  await page.clock.runFor(50)
  await expect(input).toBeFocused()
})

test('search, deletion and persisted navigation remain keyboard usable', async ({ page }, testInfo) => {
  await seedChat(page, savedChat())
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  await page.getByRole('button', { name: 'Aktionen für Gedanken 1', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Löschen', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Chat löschen?', exact: true })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Löschen', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(dialog).not.toBeVisible()
  await page.keyboard.press('Control+k')
  await page.getByPlaceholder('Chat suchen …').fill('Gedanken 1')
  await expect(page.getByRole('option', { name: 'Gedanken 1', exact: true })).toHaveCount(0)
  await page.keyboard.press('Escape')
  if (await toggle.getAttribute('aria-expanded') === 'true') await toggle.click()
  await page.reload()
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  if (testInfo.project.name === 'desktop') await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await toggle.click()
  await expect(page.getByRole('navigation', { name: 'Gespräche' })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Gespräche' }).getByRole('button', { name: 'Gedanken 1', exact: true })).toHaveCount(0)
})

test('large code, tables, URLs and untrusted Markdown remain inside the conversation', async ({ page }) => {
  const snapshot = savedChat()
  snapshot.messages['user-0']!.content = 'https://example.com/' + 'x'.repeat(1500)
  snapshot.messages['assistant-0']!.content = '# Große Inhalte\n\n<script>alert("unsafe")</script>\n\n```text\n' + 'code'.repeat(500) + '\n```\n\n| Erste Spalte | Zweite Spalte | Dritte Spalte |\n| --- | --- | --- |\n| ' + 'cell'.repeat(100) + ' | ' + 'another'.repeat(100) + ' | ' + 'value'.repeat(100) + ' |'
  await seedChat(page, snapshot)
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await expect(page.locator('.assistant-content script')).toHaveCount(0)
  const overflow = await page.evaluate(() => {
    const code = document.querySelector('.code-block pre')!
    const table = document.querySelector('.markdown-table')!
    return { page: document.documentElement.scrollWidth > innerWidth, code: code.scrollWidth > code.clientWidth, table: table.scrollWidth > table.clientWidth, windowTop: scrollY }
  })
  expect(overflow).toEqual({ page: false, code: true, table: true, windowTop: 0 })
})

for (const count of [100, 500]) {
  test(`${count} messages stay responsive and do not rerender old message nodes on streaming`, async ({ page }, testInfo) => {
    const snapshot = savedChat(count / 2)
    snapshot.messages[`assistant-${count / 2 - 1}`]!.content += '\n\n```python\n' + 'value = "a long code line that can scroll horizontally"\n'.repeat(150) + '```'
    for (let index = 0; index < 10; index++) {
      const original = snapshot.messages['assistant-0']!
      const id = `alternative-${index}`
      snapshot.messages[id] = { ...original, id, content: `Alternative Antwort ${index + 1}` }
    }
    await seedChat(page, snapshot)
    const start = Date.now()
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true', { timeout: 15_000 })
    await expect(page.locator('.chat-message')).toHaveCount(count)
    const readyMs = Date.now() - start
    const scrollToFrameMs = await page.locator('.chat-scroll').evaluate(async (element) => {
      const start = performance.now()
      element.scrollTop -= 500
      element.dispatchEvent(new Event('scroll'))
      await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
      return performance.now() - start
    })
    await page.locator('.message-user').first().evaluate(element => { element.dataset.retained = 'yes' })
    const metrics = await page.getByRole('textbox', { name: 'Nachricht', exact: true }).evaluate(async (element) => {
      if (!(element instanceof HTMLTextAreaElement)) throw new Error('Missing textarea')
      const start = performance.now()
      element.focus({ preventScroll: true }); element.value = '/lang'; element.dispatchEvent(new Event('input', { bubbles: true }))
      await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
      const memory = (performance as Performance & { memory?: { usedJSHeapSize: number } }).memory?.usedJSHeapSize
      return { inputToFrameMs: performance.now() - start, usedJSHeapSize: memory ?? null, domNodes: document.getElementsByTagName('*').length }
    })
    expect(metrics.inputToFrameMs).toBeLessThan(1000)
    const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
    await input.press('Enter')
    await expect(page.locator('.message-assistant').last()).toContainText('Gedanke')
    await expect(page.locator('.message-user').first()).toHaveAttribute('data-retained', 'yes')
    await page.getByRole('button', { name: 'Antwort stoppen', exact: true }).click()
    await expect(page.locator('[data-generation-status]')).toHaveAttribute('data-generation-status', 'cancelled')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await testInfo.attach('performance', { body: JSON.stringify({ count, readyMs, ...metrics }, null, 2), contentType: 'application/json' })
    await testInfo.attach('scroll-performance', { body: JSON.stringify({ count, scrollToFrameMs, inactiveVariants: 10 }, null, 2), contentType: 'application/json' })
  })
}

test('message editing returns keyboard focus and leaves selected text intact on cancel', async ({ page }) => {
  await seedChat(page, savedChat())
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const edit = page.getByRole('button', { name: 'Nachricht bearbeiten', exact: true })
  await edit.click()
  const dialog = page.getByRole('dialog', { name: 'Nachricht bearbeiten', exact: true })
  const input = dialog.getByRole('textbox', { name: 'Nachricht bearbeiten', exact: true })
  await expect(input).toBeFocused()
  await input.press('Control+a')
  expect(await input.evaluate(element => element instanceof HTMLTextAreaElement && element.selectionStart === 0 && element.selectionEnd === element.value.length)).toBe(true)
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await expect(edit).toBeFocused()
  await expect(page.locator('.user-bubble')).toHaveText('Wie können wir eine gute Idee weiterentwickeln?')
})
