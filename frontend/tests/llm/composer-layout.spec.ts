import { openModelChoices, expectSelectedModel } from '../e2e/model-helpers'
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { DEFAULT_CHAT_LIMITS } from '../../app/lib/chat/limits'

// Compare CSS-pixel geometry at DPR 1, like the local reference and the UI
// regression suite. Fractional device scales can snap text glyphs differently.
test.use({ deviceScaleFactor: 1 })
// Four catalog choices, keyboard verification and repeated popover captures.
test.setTimeout(60_000)

// Display names are synthetic catalog data. Provider IDs still reach only the
// existing loopback simulator; these tests cannot contact a paid provider.
const names = ['Gemma 4 31B', 'GPT-OSS 120B', 'GLM 5.3 Flash', 'Ein besonders langer synthetischer Modellname für schmale Viewports']
const ids = ['fixture-alpha', 'fixture-beta', 'fixture-long', 'fixture-extra']

async function selectModel(page: Page, name: string): Promise<void> {
  const input = page.locator('.composer-input')
  const draft = await openModelChoices(page)
  await input.press('Home')
  for (let index = 0; index < names.indexOf(name); index++) await input.press('ArrowDown')
  const option = page.getByRole('option', { name, exact: true })
  await expect(option).toBeVisible()
  await expect(input).toHaveAttribute('aria-activedescendant', await option.getAttribute('id') as string)
  const box = (await option.boundingBox())!
  expect(box.x + box.width).toBeLessThanOrEqual((await page.viewportSize())!.width)
  await input.press('Enter')
  await expect(page.locator('.composer-slash-menu')).toBeHidden()
  expect([draft, `${draft} `]).toContain(await input.inputValue())
  await input.fill(draft)
  await expectSelectedModel(page, name)
}

test.beforeEach(async ({ page, request }) => {
  const fixtureOrigin = `http://127.0.0.1:${Number(process.env.NORIS_E2E_PROVIDER_PORT ?? 8591)}`
  await request.post(`${fixtureOrigin}/fixture/catalog`, { data: { ids: ids.slice(0, 3) } })
  await page.route('**/api/v1/llm/models', route => route.fulfill({ json: {
    models: names.map((name, index) => ({ id: ids[index], name, description: '', available: true, streaming: true })),
    default_model: ids[0], status: 'ready', limits: DEFAULT_CHAT_LIMITS,
  } }))
})

async function openComposer(page: Page, theme: string, project: string): Promise<void> {
  await page.setViewportSize(project === 'desktop' ? { width: 1701, height: 863 } : { width: 390, height: 844 })
  await page.addInitScript(value => localStorage.setItem('noris-ai-theme', value), theme)
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
}

// Each visual state is a separate test so one stale baseline cannot prevent
// the other models, multiline input and Stop from producing CI evidence.
for (const theme of ['light', 'dark']) {
  for (const [captureIndex, captureName] of names.entries()) {
    test(`model changes preserve composer geometry: ${captureName} ${theme}`, async ({ page }, info) => {
      await openComposer(page, theme, info.project.name)
      const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
      const composer = page.locator('.chat-composer')
      const before = await composer.boundingBox()
      await input.fill('Testentwurf')
      for (const name of names) {
        await selectModel(page, name)
        await expect(input).toHaveValue('Testentwurf')
        await expectSelectedModel(page, name)
        expect(await composer.boundingBox()).toEqual(before)
        await expect(page.locator('.composer-model')).toHaveCount(0)
        await expect(page.locator('.chat-header')).not.toContainText(name)
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      }
      await selectModel(page, captureName)
      await input.focus()
      await expect(page).toHaveScreenshot(`composer-model-${captureIndex}-${theme}.png`, { animations: 'disabled', caret: 'hide' })
    })
  }

  test(`multiline composer visual state ${theme}`, async ({ page }, info) => {
    await openComposer(page, theme, info.project.name)
    const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
    await input.fill('Erste synthetische Zeile\nZweite synthetische Zeile\nDritte synthetische Zeile')
    await input.focus()
    await expect(page).toHaveScreenshot(`composer-multiline-${theme}.png`, { animations: 'disabled', caret: 'hide' })
  })

  test(`streaming composer visual state and Stop ${theme}`, async ({ page }, info) => {
    await openComposer(page, theme, info.project.name)
    const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
    await input.fill('Erste synthetische Zeile\nZweite synthetische Zeile\nDritte synthetische Zeile')
    await input.fill('/quiet composer-layout')
    await input.press('Enter')
    const stop = page.getByRole('button', { name: 'Antwort stoppen', exact: true })
    await expect(stop).toBeVisible()
    await expect(page.locator('[data-generation-status="streaming"]')).toBeAttached()
    try {
      await expect(page).toHaveScreenshot(`composer-streaming-${theme}.png`, { animations: 'disabled', caret: 'hide' })
    }
    finally {
      await stop.click()
      await expect(page.locator('[data-generation-status="cancelled"]')).toBeAttached()
      await expect(input).toBeFocused()
    }
  })
}

for (const viewport of [{ width: 1920, height: 975 }, { width: 1440, height: 900 }, { width: 1280, height: 800 }, { width: 768, height: 1024 }, { width: 360, height: 800 }]) {
  test(`catalog names keep one control row at ${viewport.width}x${viewport.height}`, async ({ page }, info) => {
    test.skip(info.project.name !== 'desktop', 'Supplementary viewport matrix runs once.')
    await page.setViewportSize(viewport)
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    await expectSelectedModel(page, names[0]!)
    const original = await page.locator('.chat-composer').boundingBox()
    for (const name of names) {
      await selectModel(page, name)
      expect(await page.locator('.chat-composer').boundingBox()).toEqual(original)
      await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeInViewport()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    }
  })
}
