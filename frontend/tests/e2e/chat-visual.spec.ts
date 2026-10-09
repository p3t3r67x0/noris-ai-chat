import { expect, test } from '@playwright/test'
import { savedChat, seedChat } from './chat-fixtures'

for (const theme of ['light', 'dark']) {
  test(`empty workspace visual baseline in ${theme} mode`, async ({ page }, testInfo) => {
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    page.on('console', message => { if (message.type() === 'error' || /hydration/i.test(message.text())) errors.push(message.text()) })
    const snapshot = savedChat(0)
    snapshot.conversations.activeConversationId = null
    await seedChat(page, snapshot, theme)
    await page.clock.setFixedTime(new Date('2026-10-09T12:00:00Z'))
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true', { timeout: 15_000 })
    await expect(page.locator('html')).toHaveClass(theme === 'dark' ? /dark/ : /light/)
    await page.screenshot({ path: testInfo.outputPath(`${testInfo.project.name}-${theme}.png`), animations: 'disabled' })
    await expect(page).toHaveScreenshot(`workspace-${theme}.png`, { animations: 'disabled', caret: 'hide' })
    expect(errors).toEqual([])
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}

test('active conversation and streaming screenshot artifacts', async ({ page }, testInfo) => {
  await seedChat(page, savedChat())
  await page.clock.setFixedTime(new Date('2026-10-09T12:00:00Z'))
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true', { timeout: 15_000 })
  await page.screenshot({ path: testInfo.outputPath(`${testInfo.project.name}-active.png`), animations: 'disabled' })
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.fill('/lang')
  await page.clock.install()
  await page.clock.pauseAt(new Date(await page.evaluate(() => Date.now()) + 100))
  await input.press('Enter')
  await page.clock.runFor(2500)
  await expect(page.locator('[data-generation-status]')).toHaveAttribute('data-generation-status', 'streaming')
  await page.screenshot({ path: testInfo.outputPath(`${testInfo.project.name}-streaming.png`), animations: 'disabled' })
})
