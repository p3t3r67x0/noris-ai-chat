import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { DEFAULT_CHAT_LIMITS } from '../../app/lib/chat/limits'

// Compare CSS-pixel geometry at DPR 1, like the local reference and the UI
// regression suite. Fractional device scales can snap text glyphs differently.
test.use({ deviceScaleFactor: 1 })

// Display names are synthetic catalog data. Provider IDs still reach only the
// existing loopback simulator; these tests cannot contact a paid provider.
const names = ['Gemma 4 31B', 'GPT-OSS 120B', 'GLM 5.3 Flash', 'Ein besonders langer synthetischer Modellname für schmale Viewports']
const ids = ['fixture-alpha', 'fixture-beta', 'fixture-long', 'fixture-extra']

async function selectModel(page: Page, name: string): Promise<void> {
  const menu = page.getByRole('button', { name: 'Modell im Eingabefeld auswählen', exact: true })
  if (await menu.getAttribute('title') === name) return
  await menu.focus()
  await menu.press('Enter')
  await expect(page.getByRole('option', { name, exact: true })).toBeVisible()
  await page.evaluate(async () => {
    await Promise.all(document.getAnimations().filter(animation => animation.effect && Number.isFinite(Number(animation.effect.getComputedTiming().endTime))).map(animation => animation.finished.catch(() => {})))
  })
  // Exercise the same keyboard interaction on desktop and touch devices.
  await page.getByRole('listbox').focus()
  await page.keyboard.press('Home')
  await expect(page.getByRole('option', { name: names[0]!, exact: true })).toBeFocused()
  for (let index = 0; index < names.indexOf(name); index++) {
    await page.keyboard.press('ArrowDown')
    await expect(page.getByRole('option', { name: names[index + 1]!, exact: true })).toBeFocused()
  }
  await expect(page.getByRole('option', { name, exact: true })).toBeFocused()
  await page.getByRole('option', { name, exact: true }).press('Enter')
  await expect(menu).toHaveAttribute('title', name)
  await expect(menu).toHaveAttribute('data-state', 'closed')
  await expect(page.getByRole('listbox')).toHaveCount(0)
}

test.beforeEach(async ({ page, request }) => {
  const fixtureOrigin = `http://127.0.0.1:${Number(process.env.NORIS_E2E_PROVIDER_PORT ?? 8591)}`
  await request.post(`${fixtureOrigin}/fixture/catalog`, { data: { ids: ids.slice(0, 3) } })
  await page.route('**/api/v1/llm/models', route => route.fulfill({ json: {
    models: names.map((name, index) => ({ id: ids[index], name, description: '', available: true, streaming: true })),
    default_model: ids[0], status: 'ready', limits: DEFAULT_CHAT_LIMITS,
  } }))
})

for (const theme of ['light', 'dark']) {
  test(`model changes preserve composer geometry and visual states ${theme}`, async ({ page }, info) => {
    await page.setViewportSize(info.project.name === 'desktop' ? { width: 1701, height: 863 } : { width: 390, height: 844 })
    await page.addInitScript(value => localStorage.setItem('noris-ai-theme', value), theme)
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
    const composer = page.locator('.chat-composer')
    const before = await composer.boundingBox()
    await input.fill('Testentwurf')
    for (const [index, name] of names.entries()) {
      await selectModel(page, name)
      await expect(input).toHaveValue('Testentwurf')
      await expect(page.getByRole('button', { name: 'Modell auswählen', exact: true })).toContainText(name)
      expect(await composer.boundingBox()).toEqual(before)
      const label = await page.locator('.composer-model .model-label').evaluate(element => ({
        whiteSpace: getComputedStyle(element).whiteSpace,
        height: element.getBoundingClientRect().height,
        lineHeight: Number.parseFloat(getComputedStyle(element).lineHeight),
        clipped: element.scrollWidth > element.clientWidth,
      }))
      expect(label.whiteSpace).toBe('nowrap')
      expect(label.height).toBeLessThanOrEqual(label.lineHeight + 1)
      if (info.project.name === 'desktop' && index < 3) expect(label.clipped).toBe(false)
      const textBox = await page.locator('.composer-model .model-label').boundingBox()
      const chevron = await page.locator('.composer-model [data-slot="trailing"]').boundingBox()
      expect(textBox!.x + textBox!.width).toBeLessThan(chevron!.x)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      await input.focus()
      await expect(page).toHaveScreenshot(`composer-model-${index}-${theme}.png`, { animations: 'disabled', caret: 'hide' })
    }
    await selectModel(page, names[0]!)
    await input.fill('Erste synthetische Zeile\nZweite synthetische Zeile\nDritte synthetische Zeile')
    await input.focus()
    await expect(page).toHaveScreenshot(`composer-multiline-${theme}.png`, { animations: 'disabled', caret: 'hide' })
    await input.fill('/quiet composer-layout')
    await input.press('Enter')
    const stop = page.getByRole('button', { name: 'Antwort stoppen', exact: true })
    await expect(stop).toBeVisible()
    await expect(page.locator('[data-generation-status="streaming"]')).toBeAttached()
    await expect(page).toHaveScreenshot(`composer-streaming-${theme}.png`, { animations: 'disabled', caret: 'hide' })
    await stop.click()
    await expect(page.locator('[data-generation-status="cancelled"]')).toBeAttached()
    await expect(input).toBeFocused()
  })
}

for (const viewport of [{ width: 1920, height: 975 }, { width: 1440, height: 900 }, { width: 1280, height: 800 }, { width: 768, height: 1024 }, { width: 360, height: 800 }]) {
  test(`catalog names keep one control row at ${viewport.width}x${viewport.height}`, async ({ page }, info) => {
    test.skip(info.project.name !== 'desktop', 'Supplementary viewport matrix runs once.')
    await page.setViewportSize(viewport)
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    await expect(page.locator('.composer-model')).toHaveAttribute('title', names[0]!)
    const original = await page.locator('.chat-composer').boundingBox()
    for (const name of names) {
      await selectModel(page, name)
      expect(await page.locator('.chat-composer').boundingBox()).toEqual(original)
      await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeInViewport()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    }
  })
}
