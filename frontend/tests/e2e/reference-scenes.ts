import { expect } from '@playwright/test'
import type { Page, TestInfo } from '@playwright/test'
import { codeChat, referenceChat, savedChat, seedChat } from './chat-fixtures'

function contrastRatio(foreground: string, background: string): number {
  const luminance = (color: string): number => {
    const channels = color.match(/[\d.]+/g)?.slice(0, 3).map(value => Number(value) / 255)
    if (!channels || channels.length !== 3) throw new Error(`Unrecognized computed color: ${color}`)
    const linear = channels.map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
    return linear[0]! * 0.2126 + linear[1]! * 0.7152 + linear[2]! * 0.0722
  }
  const a = luminance(foreground)
  const b = luminance(background)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

export async function captureScene(page: Page, testInfo: TestInfo, scene: string, theme: string): Promise<void> {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => { if (message.type() === 'error' || /hydration/i.test(message.text())) errors.push(message.text()) })
  const snapshot = scene === 'reference' ? referenceChat() : scene === 'code' ? codeChat() : savedChat(scene === 'empty' || scene === 'sidebar-open' || scene === 'drawer' ? 0 : scene === 'long' ? 50 : 1)
  if (scene === 'empty') snapshot.conversations.activeConversationId = null
  await seedChat(page, snapshot, theme)
  await page.clock.setFixedTime(new Date('2026-10-09T12:00:00Z'))
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true', { timeout: 15_000 })
  await expect(page.locator('html')).toHaveClass(theme === 'dark' ? /dark/ : /light/)
  const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
  if (scene === 'sidebar-closed' && await toggle.getAttribute('aria-expanded') === 'true') await toggle.click()
  if (scene === 'drawer') {
    await toggle.click()
    await expect(page.getByRole('navigation', { name: 'Gespräche' })).toBeVisible()
  }
  if (scene === 'code') await expect(page.locator('.syntax-token').first()).toBeVisible()
  if (scene === 'reference') {
    // Read the synthetic comparable answer while a genuine cancellable mock runs
    // in the next turn. No production component receives a screenshot-only state.
    const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
    await input.fill('/lang')
    await page.clock.install({ time: new Date('2026-10-09T12:00:00Z') })
    await page.clock.pauseAt(new Date(await page.evaluate(() => Date.now()) + 100))
    await input.press('Enter')
    await page.clock.runFor(1000)
    await expect(page.locator('[data-generation-status]')).toHaveAttribute('data-generation-status', 'streaming')
    await page.locator('.message-assistant h1').evaluate(element => {
      const scroll = element.closest('.chat-scroll')
      if (!(scroll instanceof HTMLElement)) throw new Error('Missing conversation scroller')
      scroll.scrollTop += element.getBoundingClientRect().top - 152
      scroll.dispatchEvent(new Event('scroll'))
    })
  }
  if (scene === 'streaming') {
    const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
    await input.fill('/lang')
    await page.clock.install({ time: new Date('2026-10-09T12:00:00Z') })
    await page.clock.pauseAt(new Date(await page.evaluate(() => Date.now()) + 100))
    await input.press('Enter')
    await page.clock.runFor(2500)
    await expect(page.locator('[data-generation-status]')).toHaveAttribute('data-generation-status', 'streaming')
  }
  await page.evaluate(() => document.fonts.ready)
  // Measure after finite drawer/overlay motion settles. Interpolated transforms
  // otherwise introduce floating-point widths just below the actual 44px target.
  await page.evaluate(async () => {
    const finite = document.getAnimations().filter(animation =>
      animation.effect && Number.isFinite(Number(animation.effect.getComputedTiming().endTime)),
    )
    await Promise.all(finite.map(animation => animation.finished.catch(() => {})))
  })
  const geometry = await page.evaluate(() => {
    const box = (selector: string) => {
      const element = document.querySelector(selector)
      const rect = element?.getBoundingClientRect()
      return rect ? { x: rect.x, y: rect.y, width: rect.width, height: rect.height } : null
    }
    const style = getComputedStyle(document.querySelector('.chat-composer textarea')!)
    const bodyStyle = getComputedStyle(document.body)
    const noteStyle = getComputedStyle(document.querySelector('.composer-note')!)
    const composerStyle = getComputedStyle(document.querySelector('.chat-composer')!)
    const touchTargets = [...document.querySelectorAll('.touch-control')].map(element => element.getBoundingClientRect()).filter(rect => rect.width > 0 && rect.height > 0).map(rect => ({ width: rect.width, height: rect.height }))
    return { viewport: { width: innerWidth, height: innerHeight, dpr: devicePixelRatio }, rail: box('.chat-rail'), sidebar: box('#chat-sidebar [data-slot="container"]'), timeline: box('.chat-timeline'), composer: box('.chat-composer'), header: box('.chat-header'), typography: { family: style.fontFamily, size: style.fontSize, lineHeight: style.lineHeight }, colors: { text: bodyStyle.color, background: bodyStyle.backgroundColor, secondary: noteStyle.color, composerText: style.color, composerBackground: composerStyle.backgroundColor }, touchTargets, bodyScroll: scrollY, overflow: document.documentElement.scrollWidth > innerWidth }
  })
  expect(geometry.overflow).toBe(false)
  expect(geometry.bodyScroll).toBe(0)
  expect(errors).toEqual([])
  const colors = geometry.colors
  const contrast = { primary: contrastRatio(colors.text, colors.background), secondary: contrastRatio(colors.secondary, colors.background), composer: contrastRatio(colors.composerText, colors.composerBackground) }
  for (const ratio of Object.values(contrast)) expect(ratio).toBeGreaterThanOrEqual(4.5)
  for (const target of geometry.touchTargets) {
    expect(target.width).toBeGreaterThanOrEqual(44)
    expect(target.height).toBeGreaterThanOrEqual(44)
  }
  await testInfo.attach('accessibility', { body: JSON.stringify({ contrast, touchTargets: geometry.touchTargets }, null, 2), contentType: 'application/json' })
  await testInfo.attach('geometry', { body: JSON.stringify(geometry, null, 2), contentType: 'application/json' })
  const name = `${scene}-${theme}.png`
  await page.screenshot({ path: testInfo.outputPath(name), animations: 'disabled', caret: 'hide' })
  await expect(page).toHaveScreenshot(`reference-${name}`, { animations: 'disabled', caret: 'hide' })
}
