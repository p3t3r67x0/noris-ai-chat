import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { clearTestConversations, stableModelCatalog } from './chat-fixtures'

test.beforeEach(async ({ page, request }) => {
  await stableModelCatalog(page)
  await clearTestConversations(request)
  await request.put('/api/v1/chat/drafts/new', { data: { content: '' } })
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null, modelId: null } })
})

async function search(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Anhänge und Werkzeuge', exact: true }).click()
  await page.getByRole('menuitem', { name: /^Websuche/ }).click()
  await expect(page.locator('.composer-web-search')).toBeVisible()
}

for (const viewport of [{ width: 1920, height: 975 }, { width: 1440, height: 900 }, { width: 768, height: 1024 }, { width: 390, height: 844 }, { width: 320, height: 740 }]) {
  for (const theme of ['light', 'dark']) {
    test(`compact composer screenshots ${viewport.width} ${theme}`, async ({ page }, info) => {
      test.setTimeout(60_000) // Eight screenshots plus the real fixture lifecycle share one browser session.
      test.skip(info.project.name === 'mobile' && viewport.width !== 390, 'Touch interaction runs at phone width; the desktop project covers the full matrix.')
      await page.setViewportSize(viewport)
      await page.addInitScript(value => localStorage.setItem('noris-ai-theme', value), theme)
      await page.goto('/')
      await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      const composer = page.locator('.chat-composer')
      const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
      await input.focus()
      await input.evaluate(element => { element.dataset.instance = 'original' })
      const original = (await composer.boundingBox())!
      const controls = ['.composer-attachment', '.composer-model', '.composer-microphone', '.composer-submit']
      const positions = await Promise.all(controls.map(selector => page.locator(selector).boundingBox()))
      const singleLine = await input.evaluate(element => element.clientHeight)
      if (viewport.width === 1920) {
        // October CSS targets are distinct from the supplied 1920 × 975 image pixels.
        expect(original.width).toBeCloseTo(888, 0)
        expect(original.height).toBeCloseTo(62, 0)
        expect(original.y + original.height).toBeCloseTo(975 * 0.49 + 4, 0)
        expect(await input.evaluate(element => Number.parseFloat(getComputedStyle(element).fontSize))).toBeCloseTo(18, 1)
      }

      async function geometry(): Promise<void> {
        const metrics = await page.evaluate(selectors => {
          const box = (selector: string) => {
            const { x, y, width, height } = document.querySelector(selector)!.getBoundingClientRect()
            return { x, y, width, height }
          }
          const root = document.querySelector('.chat-composer')!
          return {
            composer: box('.chat-composer'), input: box('.composer-input'), model: box('.composer-model'),
            controls: selectors.map(box),
            pageFits: scrollX === 0 && scrollY === 0 && document.documentElement.scrollWidth <= innerWidth,
            composerFits: root.scrollWidth <= root.clientWidth,
          }
        }, controls)
        const box = metrics.composer
        expect(box.y + box.height).toBeCloseTo(original.y + original.height, 0)
        for (const [index, control] of metrics.controls.entries()) {
          expect(control.x).toBeCloseTo(positions[index]!.x, 0)
          expect(control.y).toBeCloseTo(positions[index]!.y, 0)
          expect(control.x + control.width).toBeLessThanOrEqual(box.x + box.width)
        }
        expect(metrics.input.y + metrics.input.height <= metrics.model.y || metrics.input.x + metrics.input.width <= metrics.model.x).toBe(true)
        expect(metrics.pageFits).toBe(true)
        expect(metrics.composerFits).toBe(true)
        await expect(input).toBeFocused()
        await expect(input).toHaveAttribute('data-instance', 'original')
      }
      async function screenshot(state: string): Promise<void> {
        await geometry()
        await expect(composer).toHaveScreenshot(`compact-${viewport.width}-${theme}-${state}.png`, { animations: 'disabled', caret: 'hide' })
      }

      await screenshot('empty')
      await input.fill('Kurze Frage')
      await screenshot('single-line')
      await search(page)
      await expect(input).toHaveValue('Kurze Frage')
      await expect(page.locator('.composer-files')).toHaveCount(0)
      await expect(page.locator('.composer-body .composer-web-search')).toBeVisible()
      expect(await input.evaluate(element => element.clientHeight)).toBe(singleLine)
      expect((await composer.boundingBox())!.height).toBe(original.height)
      await screenshot('web-search')
      await page.getByRole('button', { name: 'Websuche deaktivieren', exact: true }).click()
      await expect(page.locator('.composer-web-search')).toHaveCount(0)
      await expect(input).toHaveValue('Kurze Frage')
      await geometry()

      const multiline = 'Erste Zeile\nZweite Zeile\nDritte Zeile\nVierte Zeile'
      await input.fill(multiline)
      await expect(page.locator('.composer-container')).toHaveAttribute('data-layout', 'expanded')
      await screenshot('multiline')
      await search(page)
      await expect(input).toHaveValue(multiline)
      await screenshot('multiline-web-search')

      await input.fill(Array.from({ length: 40 }, (_, index) => `Zeile ${index + 1}`).join('\n'))
      await expect(page.locator('.composer-container')).toHaveAttribute('data-layout', 'maximized')
      expect(await input.evaluate(element => element.scrollHeight > element.clientHeight && getComputedStyle(element).overflowY === 'auto' && element.scrollWidth <= element.clientWidth)).toBe(true)
      await screenshot('scroll-limit')
      await input.fill('Kurz')
      await expect(page.locator('.composer-container')).toHaveAttribute('data-layout', 'compact')
      expect((await composer.boundingBox())!.height).toBe(original.height)
      await screenshot('shrunk-web-search')
      await page.getByRole('button', { name: 'Websuche deaktivieren', exact: true }).click()
      await input.fill('')
      expect(await composer.boundingBox()).toEqual(original)
      await screenshot('shrunk-empty')

      const colors = await page.locator('.composer-submit').evaluate(element => ({ background: getComputedStyle(element).backgroundColor, color: getComputedStyle(element).color }))
      expect(colors).toEqual(theme === 'dark'
        ? { background: 'rgb(236, 236, 236)', color: 'rgb(21, 21, 21)' }
        : { background: 'rgb(13, 13, 13)', color: 'rgb(255, 255, 255)' })
      await expect(page.locator('.composer-microphone')).toHaveAccessibleName('Diktieren')
    })
  }
}
