import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import { holdLoadingPath, seedLoadingChats } from './loading-fixtures'

const evidence = fileURLToPath(new URL('../../../docs/ui-reference/loading-spinner', import.meta.url))
test.use({ deviceScaleFactor: 1 })
test.setTimeout(60_000)
const status = (page: Page) => page.getByRole('status', { name: 'Chat wird geladen', exact: true })

async function centered(page: Page) {
  await expect(status(page)).toBeVisible()
  await expect(status(page)).toHaveText('')
  const measurements = await page.evaluate(() => {
    const pane = document.querySelector('.chat-content')!.getBoundingClientRect()
    const ring = document.querySelector('.chat-loading-spinner')!
    const rect = ring.getBoundingClientRect()
    const style = getComputedStyle(ring.querySelector('.chat-loading-ring')!)
    const arc = getComputedStyle(ring.querySelector('.chat-loading-arc')!)
    return { viewport: { width: innerWidth, height: innerHeight, dpr: devicePixelRatio }, pane: pane.toJSON(), spinner: rect.toJSON(),
      centerDeltaX: rect.x + rect.width / 2 - (pane.x + pane.width / 2), centerDeltaY: rect.y + rect.height / 2 - (pane.y + pane.height / 2),
      styles: { stroke: arc.strokeWidth, color: arc.stroke, animation: style.animationName, duration: style.animationDuration, timing: style.animationTimingFunction, iterations: style.animationIterationCount } }
  })
  expect(measurements.spinner.width).toBe(20)
  expect(measurements.spinner.height).toBe(20)
  expect(measurements.styles.stroke).toBe('2.5px')
  expect(measurements.centerDeltaX).toBeCloseTo(0, 1)
  expect(measurements.centerDeltaY).toBeCloseTo(0, 1)
  return measurements
}

test('reference raster scale places the ring at the measured center below the header', async ({ browser, request }, info) => {
  test.skip(info.project.name !== 'desktop', 'Reference normalization runs once, independently of touch emulation.')
  // The reference visibly shows 130% browser zoom; rail 68px / CSS 52px confirms
  // the effective scale. This reproduces that raster scale, not unknown browser metadata.
  const context = await browser.newContext({ viewport: { width: 1477, height: 751 }, deviceScaleFactor: 1.3, locale: 'de-DE', reducedMotion: 'reduce', colorScheme: 'light' })
  try {
    const page = await context.newPage()
    await page.addInitScript(() => { localStorage.setItem('noris-ai-theme', 'light'); localStorage.setItem('noris-ai:sidebar-open', 'true') })
    const chats = await seedLoadingChats(page, request)
    const gate = await holdLoadingPath(page, chats.first)
    await page.goto(process.env.NORIS_E2E_COMPOSE_URL ?? `http://127.0.0.1:${process.env.NORIS_E2E_FRONTEND_PORT ?? 8593}`)
    await gate.hit
    const geometry = await centered(page)
    const rasterCenter = { x: (geometry.spinner.x + geometry.spinner.width / 2) * 1.3, y: (geometry.spinner.y + geometry.spinner.height / 2) * 1.3 }
    expect(Math.abs(rasterCenter.x - 1181.5)).toBeLessThan(1)
    expect(Math.abs(rasterCenter.y - 521.5)).toBeLessThan(1)
    await mkdir(evidence, { recursive: true })
    await writeFile(resolve(evidence, 'reference-normalized-geometry.json'), JSON.stringify({ ...geometry, rasterCenter, referenceCenter: { x: 1181.5, y: 521.5 }, referenceBrowserContentTop: 85, scale: 1.3, note: 'Raster-scale reconstruction; original CSS viewport and DPR are not recorded in the PNG.' }, null, 2) + '\n')
    await page.screenshot({ path: resolve(evidence, 'reference-normalized-after.png'), animations: 'disabled', caret: 'hide' })
    gate.release()
    await expect(status(page)).toHaveCount(0)
  }
  finally { await context.close() }
})

for (const [width, height] of [[1920, 976], [1701, 863], [1440, 900], [390, 844]] as const) {
  for (const theme of ['light', 'dark']) for (const sidebar of [true, false]) {
    test(`conversation loading ${width} ${theme} sidebar ${sidebar ? 'open' : 'closed'}`, async ({ page, request }, info) => {
      test.skip(width === 390 && sidebar, 'The mobile drawer starts closed; its opening interaction is tested separately.')
      test.skip(info.project.name === 'mobile' && width !== 390, 'Explicit viewport matrix runs once; touch runs at phone width.')
      await page.setViewportSize({ width, height })
      await page.emulateMedia({ colorScheme: theme as 'light' | 'dark', reducedMotion: 'reduce' })
      await page.addInitScript(({ theme, sidebar }) => { localStorage.setItem('noris-ai-theme', theme); localStorage.setItem('noris-ai:sidebar-open', String(sidebar)) }, { theme, sidebar })
      const chats = await seedLoadingChats(page, request)
      const id = sidebar ? chats.first : chats.second
      const gate = await holdLoadingPath(page, id)
      await page.goto(sidebar ? '/' : `/?conversationId=${id}`)
      await gate.hit
      await page.evaluate(() => document.fonts.ready)
      const geometry = await centered(page)
      await expect(page.locator('.chat-message-pane')).toHaveAttribute('data-loading-state', 'initial')
      if (width >= 1024) {
        expect(geometry.pane.x).toBe(sidebar ? 340 : 52)
        await expect(page.locator('.chat-rail')).toBeVisible()
      }
      expect(geometry.styles.animation).toBe('none')
      const input = page.locator('.composer-input')
      const original = await input.elementHandle()
      const composer = (await page.locator('.chat-composer').boundingBox())!
      await mkdir(evidence, { recursive: true })
      await expect(page).toHaveScreenshot(`loading-${width}-${theme}-${sidebar ? 'open' : 'closed'}.png`, { animations: 'disabled', caret: 'hide' })
      await page.screenshot({ path: resolve(evidence, `loading-${width}-${theme}-${sidebar ? 'open' : 'closed'}.png`), animations: 'disabled', caret: 'hide' })
      if (width === 1920 && theme === 'light' && sidebar) await page.screenshot({ path: resolve(evidence, 'loading-after.png'), animations: 'disabled', caret: 'hide' })
      await writeFile(resolve(evidence, `geometry-${width}-${theme}-${sidebar ? 'open' : 'closed'}-${info.project.name}.json`), JSON.stringify(geometry, null, 2) + '\n')
      gate.release()
      await expect(status(page)).toHaveCount(0)
      await expect(page.locator('.message-assistant').last()).toContainText(`Synthetischer Verlauf ${sidebar ? 'A' : 'B'}`)
      await expect(input).toHaveValue(`Gespeicherter Entwurf ${sidebar ? 'A' : 'B'}`)
      expect(await original!.evaluate(element => element === document.querySelector('.composer-input'))).toBe(true)
      const loaded = (await page.locator('.chat-composer').boundingBox())!
      expect(loaded.y + loaded.height).toBeCloseTo(composer.y + composer.height, 0)
      expect(gate.requests).toBe(1)
      gate.reset()
      await page.reload()
      await gate.hit
      await centered(page)
      gate.release()
      await expect(status(page)).toHaveCount(0)
      expect(gate.requests).toBe(2)
    })
  }
}

test('sidebar navigation loads one existing conversation and preserves restored reading positions', async ({ page, request }) => {
  const chats = await seedLoadingChats(page, request)
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const input = page.locator('.composer-input')
  const original = await input.elementHandle()
  const scroller = page.locator('.chat-scroll')
  await scroller.hover()
  await page.mouse.wheel(0, -400)
  await expect(page.getByRole('button', { name: 'Zum Ende scrollen', exact: true })).toBeVisible()
  const top = await scroller.evaluate(element => element.scrollTop)
  const gate = await holdLoadingPath(page, chats.second)
  const toggle = page.getByRole('button', { name: 'Sidebar öffnen', exact: true })
  if (await toggle.isVisible()) await toggle.click()
  await page.getByRole('button', { name: 'Ladetest B', exact: true }).click()
  await gate.hit
  await centered(page)
  await expect(page.locator('.chat-message-pane')).toHaveAttribute('data-loading-state', 'conversation')
  gate.release()
  await expect(status(page)).toHaveCount(0)
  await expect(input).toHaveValue('Gespeicherter Entwurf B')
  if (await toggle.isVisible()) await toggle.click()
  await page.getByRole('button', { name: 'Ladetest A', exact: true }).click()
  await expect(input).toHaveValue('Gespeicherter Entwurf A')
  await expect.poll(() => scroller.evaluate(element => element.scrollTop)).toBeCloseTo(top, 0)
  expect(await original!.evaluate(element => element === document.querySelector('.composer-input'))).toBe(true)
})

for (const scope of ['initial', 'conversation']) test(`a failed ${scope} load replaces the spinner with retry and recovers`, async ({ page, request }) => {
  const chats = await seedLoadingChats(page, request)
  if (scope === 'conversation') {
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  }
  const gate = await holdLoadingPath(page, scope === 'initial' ? chats.first : chats.second)
  if (scope === 'initial') await page.goto('/')
  else {
    const toggle = page.getByRole('button', { name: 'Sidebar öffnen', exact: true })
    if (await toggle.isVisible()) await toggle.click()
    await page.getByRole('button', { name: 'Ladetest B', exact: true }).click()
  }
  await gate.hit
  await centered(page)
  gate.fail()
  await expect(status(page)).toHaveCount(0)
  await expect(page.locator('.chat-message-pane').getByRole('alert')).toContainText('Chat konnte nicht geladen werden.')
  gate.reset()
  await page.locator('.chat-message-pane').getByRole('button', { name: 'Chat erneut laden', exact: true }).click()
  await gate.hit
  await centered(page)
  gate.release()
  await expect(status(page)).toHaveCount(0)
  await expect(page.locator('.message-assistant').last()).toBeVisible()
})

test('older history pagination retains the timeline without the centered spinner', async ({ page, request }) => {
  const chats = await seedLoadingChats(page, request, 80)
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await expect(page.locator('.chat-message-pane')).toHaveAttribute('data-loading-state', 'idle')
  await expect(page.locator('.chat-message')).toHaveCount(50)
  const initial = await page.locator('.chat-message').count()
  const gate = await holdLoadingPath(page, chats.first)
  await page.getByRole('button', { name: 'Ältere Nachrichten laden', exact: true }).click()
  await gate.hit
  await expect(page.locator('.chat-message-pane')).toHaveAttribute('data-loading-state', 'pagination')
  await expect(status(page)).toHaveCount(0)
  await expect(page.locator('.chat-message')).toHaveCount(initial)
  gate.release()
  await expect(page.locator('.chat-message')).toHaveCount(80)
})

test('streaming and its preserved refresh never show the global spinner; reduced motion is respected', async ({ page, request }) => {
  await seedLoadingChats(page, request)
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await page.evaluate(() => {
    const pane = document.querySelector('.chat-content')!
    pane.setAttribute('data-spinner-observations', '0')
    new MutationObserver(records => {
      const added = records.some(record => [...record.addedNodes].some(node => node instanceof Element && (node.matches('.chat-loading-region') || node.querySelector('.chat-loading-region'))))
      if (added) pane.setAttribute('data-spinner-observations', String(Number(pane.getAttribute('data-spinner-observations')) + 1))
    }).observe(pane, { childList: true, subtree: true })
  })
  await page.locator('.composer-input').fill('/quiet loading-spinner-test')
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
  await page.locator('.composer-input').press('Enter')
  await expect(page.locator('[data-generation-status="streaming"]')).toBeAttached()
  await expect(status(page)).toHaveCount(0)
  await page.getByRole('button', { name: 'Antwort stoppen', exact: true }).click()
  await expect(page.locator('[data-generation-status="cancelled"]')).toBeAttached()
  await expect(page.locator('.chat-content')).toHaveAttribute('data-spinner-observations', '0')
})

test('the reference-sized ring rotates continuously and stops with reduced motion', async ({ page, request }) => {
  const chats = await seedLoadingChats(page, request)
  const gate = await holdLoadingPath(page, chats.first)
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await page.goto('/')
  await gate.hit
  const geometry = await centered(page)
  expect(geometry.styles.duration).toBe('0.9s')
  expect(geometry.styles.timing).toBe('linear')
  expect(geometry.styles.iterations).toBe('infinite')
  const transform = () => page.locator('.chat-loading-ring').evaluate(element => getComputedStyle(element).transform)
  const before = await transform()
  await expect.poll(transform).not.toBe(before)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await expect.poll(() => page.locator('.chat-loading-ring').evaluate(element => getComputedStyle(element).animationName)).toBe('none')
  gate.release()
})


test('an unavailable direct conversation URL shows its error instead of restoring another chat', async ({ page, request }) => {
  const chats = await seedLoadingChats(page, request)
  await page.goto('/?conversationId=10000000-0000-4000-8000-999999999999')
  await expect(page.locator('.chat-message-pane').getByRole('alert')).toContainText('Chat konnte nicht geladen werden.')
  await expect(status(page)).toHaveCount(0)
  await expect(page.locator('.message-assistant')).toHaveCount(0)
  await expect(page.locator('.chat-message-pane').getByRole('button', { name: 'Chat erneut laden', exact: true })).toBeVisible()
  const gate = await holdLoadingPath(page, chats.first)
  const toggle = page.getByRole('button', { name: 'Sidebar öffnen', exact: true })
  if (await toggle.isVisible()) await toggle.click()
  await page.getByRole('button', { name: 'Ladetest A', exact: true }).click()
  await gate.hit
  await centered(page)
  gate.release()
  await expect(status(page)).toHaveCount(0)
  await expect(page.locator('.message-assistant').last()).toContainText('Synthetischer Verlauf A')
})

test('reload and initial retry restore an older saved anchor before revealing the timeline', async ({ page, request }, info) => {
  const chats = await seedLoadingChats(page, request, 80)
  await page.goto('/')
  await expect(page.locator('.chat-message-pane')).toHaveAttribute('data-loading-state', 'idle')
  await page.getByRole('button', { name: 'Ältere Nachrichten laden', exact: true }).click()
  await expect(page.locator('.chat-message')).toHaveCount(80)
  const scroller = page.locator('.chat-scroll')
  await scroller.evaluate(element => {
    element.dispatchEvent(new WheelEvent('wheel', { deltaY: -100 }))
    element.scrollTop = 0
    element.dispatchEvent(new Event('scroll'))
  })
  const oldest = page.locator(`[data-message-id="${chats.messages[0]!.id}"]`)
  await expect(oldest).toBeInViewport()
  await expect.poll(() => page.evaluate(id => {
    const positions = JSON.parse(localStorage.getItem('noris-ai:chat-scroll:v1') ?? '[]')
    return positions.find((entry: [string, { messageId: string }]) => entry[0] === id)?.[1]?.messageId
  }, chats.first)).toBe(chats.messages[0]!.id)
  const offset = (await oldest.boundingBox())!.y - (await scroller.boundingBox())!.y
  const snapshot = () => page.evaluate(id => {
    const scroller = document.querySelector('.chat-scroll')!
    const message = document.querySelector(`[data-message-id="${id}"]`)
    return { top: scroller.scrollTop, height: scroller.scrollHeight, viewport: scroller.clientHeight,
      scroller: scroller.getBoundingClientRect().toJSON(), message: message?.getBoundingClientRect().toJSON(),
      anchors: JSON.parse(localStorage.getItem('noris-ai:chat-scroll:v1') ?? '[]') }
  }, chats.messages[0]!.id)
  const before = await snapshot()
  const gate = await holdLoadingPath(page, chats.first)
  await page.reload()
  await gate.hit
  await centered(page)
  gate.fail()
  await expect(page.locator('.chat-message-pane').getByRole('alert')).toBeVisible()
  gate.reset()
  await page.locator('.chat-message-pane').getByRole('button', { name: 'Chat erneut laden', exact: true }).click()
  await gate.hit
  await centered(page)
  gate.release()
  await expect(status(page)).toHaveCount(0)
  await mkdir(evidence, { recursive: true })
  await writeFile(resolve(evidence, `scroll-retry-${info.project.name}.json`), JSON.stringify({ before, after: await snapshot() }, null, 2) + '\n')
  await expect(oldest).toBeInViewport()
  await expect.poll(async () => (await oldest.boundingBox())!.y - (await scroller.boundingBox())!.y).toBeCloseTo(offset, 0)
})
