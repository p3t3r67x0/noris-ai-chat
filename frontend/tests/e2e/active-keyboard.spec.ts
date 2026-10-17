import { expect, test } from '@playwright/test'
import { pauseBeforeGeneration, savedChat, seedChat } from './chat-fixtures'

for (const theme of ['light', 'dark']) {
  for (const streaming of [false, true]) {
    test(`${streaming ? 'streaming' : 'active'} long draft preserves messages above the keyboard ${theme}`, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 })
      await seedChat(page, savedChat(20), theme)
      await page.goto('/')
      await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      const input = page.locator('.composer-input')
      await input.evaluate(element => { element.dataset.retained = 'keyboard-editor' })
      if (streaming) {
        await pauseBeforeGeneration(page)
        await input.fill('/lang')
        await input.press('Enter')
        await page.clock.runFor(1500)
        await expect(page.locator('[data-generation-status="streaming"]')).toBeAttached()
      }
      const draft = 'Synthetischer Entwurf\n'.repeat(40)
      await input.fill(draft)
      for (const height of [360, 250]) {
        await page.evaluate(height => {
          Object.defineProperty(visualViewport!, 'height', { configurable: true, value: height })
          Object.defineProperty(visualViewport!, 'offsetTop', { configurable: true, value: 20 })
          visualViewport!.dispatchEvent(new Event('resize'))
        }, height)
        if (streaming) await page.clock.runFor(100)
        await expect.poll(() => page.locator('.chat-workspace').evaluate(element => element.getBoundingClientRect().height)).toBe(height)
        const composer = (await page.locator('.chat-composer').boundingBox())!
        expect(composer.y).toBeGreaterThanOrEqual(20)
        expect(composer.y + composer.height).toBeLessThanOrEqual(height + 20)
        // Preserve room for text and the existing message action targets.
        expect((await page.locator('.chat-scroll').boundingBox())!.height).toBeGreaterThanOrEqual(80)
        // Wait for native ResizeObserver delivery and its scheduled scroll frame
        // while the clock is paused. A tall scroller alone can still show only
        // trailing padding, so require a full line of actual response content.
        await expect.poll(async () => {
          if (streaming) await page.clock.runFor(50)
          const response = (await page.locator('.message-assistant .assistant-content').last().boundingBox())!
          const timeline = (await page.locator('.chat-scroll').boundingBox())!
          return Math.min(response.y + response.height, timeline.y + timeline.height) - Math.max(response.y, timeline.y)
        }).toBeGreaterThanOrEqual(24)
        await expect(input).toBeFocused()
        await expect(input).toHaveValue(draft)
        await expect(input).toHaveAttribute('data-retained', 'keyboard-editor')
        // Completed synthetic text gives stable visual evidence. The streaming
        // variant checks the same geometry with the real mock generation active.
        if (!streaming) await expect(page.locator('.chat-workspace')).toHaveScreenshot(`active-keyboard-${height}-${theme}.png`, { animations: 'disabled', caret: 'hide' })
      }
      await page.evaluate(() => {
        Object.defineProperty(visualViewport!, 'height', { configurable: true, value: 844 })
        Object.defineProperty(visualViewport!, 'offsetTop', { configurable: true, value: 0 })
        visualViewport!.dispatchEvent(new Event('resize'))
      })
      if (streaming) await page.clock.runFor(100)
      await expect(page.locator('.composer-note')).toBeVisible()
      await expect(input).toBeFocused()
      await expect(input).toHaveValue(draft)
      if (streaming) {
        await page.getByRole('button', { name: 'Antwort stoppen', exact: true }).click()
        await page.clock.runFor(100)
        await expect(page.locator('[data-generation-status="cancelled"]')).toBeAttached()
      }
    })
  }
}
