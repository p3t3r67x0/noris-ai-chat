import { expect, test } from '@playwright/test'
import { savedChat, seedChat } from './chat-fixtures'
import { openModelChoices, expectSelectedModel } from './model-helpers'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const scrollEvidence = fileURLToPath(new URL('../../../docs/ui-reference/final-parity/scroll', import.meta.url))

test.use({ deviceScaleFactor: 1 })
for (const [width, height] of [[1920, 976], [1701, 863], [1440, 900], [390, 844]]) {
  for (const theme of ['light', 'dark']) {
    test(`final parity ${width} ${theme}`, async ({ page }, info) => {
      // This case exercises four screenshot states plus search and scroll transitions.
      test.setTimeout(60_000)
      test.skip(info.project.name !== 'desktop', 'Explicit DPR 1 viewport matrix.')
      await page.setViewportSize({ width: width!, height: height! })
      await page.emulateMedia({ reducedMotion: 'reduce' })
      const snapshot = savedChat(8)
      snapshot.messages['assistant-7']!.content += '\n\n| Schritt | Ergebnis |\n| --- | --- |\n| Planen | Klare Frage |\n| Prüfen | Nächster Schritt |'
      await seedChat(page, snapshot, theme)
      const errors: string[] = []
      page.on('pageerror', error => errors.push(error.message))
      await page.goto('/')
      await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      await expect(page.locator('.composer-model')).toHaveCount(0)
      await expect(page.locator('.chat-header [aria-haspopup="listbox"]')).toHaveCount(0)
      const input = page.locator('.composer-input')
      const original = await input.elementHandle()
      const composer = page.locator('.chat-composer')
      const rect = (await composer.boundingBox())!
      if (width! >= 1024) {
        expect(rect.width).toBe(768)
        expect(rect.height).toBe(54)
        await expect(page.locator('.chat-header [aria-controls="chat-sidebar"]')).toBeHidden()
        expect((await page.locator('.chat-timeline').boundingBox())!.x).toBe(rect.x)
      }
      expect(await page.locator('.message-assistant').first().evaluate(element => getComputedStyle(element).fontSize)).toBe('16px')
      await input.fill('Mein Entwurf ')
      await openModelChoices(page)
      await expect(page.locator('.composer-slash-menu .model-choice-check')).toHaveCount(1)
      await expect(input).toBeFocused()
      await expect(page.locator('.composer-slash-menu')).toHaveScreenshot(`final-model-${width}-${theme}.png`, { animations: 'disabled', caret: 'hide' })
      await page.getByRole('option', { name: /noris Fast/ }).click()
      await expect(input).toHaveValue('Mein Entwurf ')
      await expectSelectedModel(page, /noris Fast/)
      expect(await original!.evaluate(node => node === document.querySelector('.composer-input'))).toBe(true)
      await input.fill('')
      const bottom = (await composer.boundingBox())!.y + (await composer.boundingBox())!.height
      await input.fill('Erste Zeile\nZweite Zeile\nDritte Zeile\nVierte Zeile')
      const expanded = (await composer.boundingBox())!
      expect(expanded.height).toBeGreaterThan(rect.height)
      expect(expanded.y + expanded.height).toBeCloseTo(bottom, 0)
      await expect(input).toBeFocused()
      await expect(page).toHaveScreenshot(`final-expanded-${width}-${theme}.png`, { animations: 'disabled', caret: 'hide' })
      const scroller = page.locator('.chat-scroll')
      await scroller.hover()
      await page.mouse.wheel(0, -600)
      await expect(page.getByRole('button', { name: 'Zum Ende scrollen' })).toBeVisible()
      const scrollMeasurements = await page.locator('.scroll-to-bottom').evaluate(element => {
        const style = getComputedStyle(element)
        return { rect: element.getBoundingClientRect().toJSON(), styles: Object.fromEntries(
          ['font-size', 'line-height', 'font-weight', 'padding', 'margin', 'border-radius', 'background', 'box-shadow'].map(key => [key, style.getPropertyValue(key)]),
        ) }
      })
      await mkdir(scrollEvidence, { recursive: true })
      await writeFile(resolve(scrollEvidence, `geometry-${width}-${theme}.json`), JSON.stringify({ width, height, dpr: 1, theme, scrollToBottom: scrollMeasurements }, null, 2) + '\n')
      const top = await scroller.evaluate(element => element.scrollTop)
      await input.fill('Weiterer\nmehrzeiliger\nEntwurf')
      expect(await scroller.evaluate(element => element.scrollTop)).toBeCloseTo(top, 0)
      await input.fill('')
      await expect(composer).toHaveCSS('height', width! >= 1024 ? '54px' : '96px')
      await page.getByRole('button', { name: 'Zum Ende scrollen' }).click()
      await expect(page.locator('.markdown-table').last()).toBeInViewport()
      if (width! >= 1024) {
        await page.getByRole('button', { name: 'Gesprächsliste schließen', exact: true }).click()
        await expect(page.locator('.chat-header').getByRole('button', { name: 'Neuer Chat', exact: true })).toBeVisible()
        const closed = (await composer.boundingBox())!
        expect(closed.x + closed.width / 2).toBe((width! + 52) / 2)
        await page.getByRole('button', { name: 'Sidebar öffnen', exact: true }).focus()
        await page.keyboard.press('Enter')
        await expect(page.locator('.conversation-sidebar')).toHaveAttribute('aria-hidden', 'false')
      }
      await input.focus()
      await page.keyboard.press('Control+k')
      const search = page.getByRole('combobox', { name: 'Chats suchen', exact: true })
      await expect(search).toBeFocused()
      await search.fill('Nächster Schritt')
      await expect(page.getByRole('option', { name: /Unser Gespräch/ })).toBeVisible()
      await expect(page.locator('.chat-search-dialog')).toHaveScreenshot(`final-search-${width}-${theme}.png`, { animations: 'disabled', caret: 'hide' })
      await search.press('ArrowDown')
      await search.press('Enter')
      await expect(page.locator('[data-message-id="assistant-7"]')).toBeFocused()
      await page.keyboard.press('Control+Shift+o')
      await expect(page.locator('.empty-chat')).toBeVisible()
      await expect(input).toBeFocused()
      expect(await original!.evaluate(node => node === document.querySelector('.composer-input'))).toBe(true)
      await expect(page).toHaveScreenshot(`final-new-chat-${width}-${theme}.png`, { animations: 'disabled', caret: 'hide' })
      expect(errors).toEqual([])
    })
  }
}
