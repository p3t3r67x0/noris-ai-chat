import { expect, test } from '@playwright/test'
import { resolve } from 'node:path'

const fixtureOrigin = `http://127.0.0.1:${process.env.NORIS_E2E_PROVIDER_PORT ?? 8591}`
const gpt = 'vllm/release/gpt-oss-120b'
const glm = 'vllm/release/glm-5-2'
const otherModels = ['GLM 5.3 Flash', 'DeepSeek V4.1 Flash', 'Qwen3.8 27B', 'Qwen3.6 27B', 'Gemma 4 31B']
const ids = [gpt, glm, 'vllm/qsu/glm-5-3-flash', 'vllm/qsu/deepseek-v41-flash', 'vllm/qsu/qwen3.8-27b', 'vllm/release/qwen3.6-27b', 'vllm/release/gemma-4-31b-it']
type ProviderCall = { model: string, max_tokens: number, reasoning_effort?: string, chat_template_kwargs?: { reasoning_effort: string } }

for (const viewport of [{ width: 1700, height: 900 }, { width: 1440, height: 900 }, { width: 768, height: 1024 }, { width: 390, height: 844 }]) {
  for (const theme of ['light', 'dark']) {
    test(`reasoning selection ${viewport.width} ${theme}`, async ({ page, request }, info) => {
      test.skip(info.project.name !== 'desktop', 'Each viewport and theme is checked once.')
      await request.post(`${fixtureOrigin}/fixture/catalog`, { data: { ids } })
      await expect.poll(async () => (await (await request.get('/api/v1/llm/models')).json()).models.map((model: { id: string }) => model.id).sort()).toEqual([...ids].sort())
      await page.setViewportSize(viewport)
      await page.emulateMedia({ reducedMotion: 'reduce' })
      await page.addInitScript(({ theme, model }) => { localStorage.setItem('noris-ai-theme', theme); localStorage.setItem('noris-ai:model', model) }, { theme, model: glm })
      await page.goto('/')
      await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
      const composer = page.locator('.chat-composer')
      const send = page.locator('.composer-submit')
      const modelMenu = page.getByRole('button', { name: 'Modell im Eingabefeld auswählen', exact: true })
      await input.fill('Eine Frage\nmit Kontext')
      await expect(page.locator('.composer-container')).toHaveAttribute('data-layout', 'expanded')
      const initialComposer = (await composer.boundingBox())!
      const initialSend = (await send.boundingBox())!
      async function geometry() {
        const box = (await composer.boundingBox())!
        const button = (await send.boundingBox())!
        expect(box.x).toBeCloseTo(initialComposer.x, 0)
        expect(box.width).toBeCloseTo(initialComposer.width, 0)
        expect(box.y + box.height).toBeCloseTo(initialComposer.y + initialComposer.height, 0)
        expect(button.x).toBeCloseTo(initialSend.x, 0)
        expect(button.y).toBeCloseTo(initialSend.y, 0)
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
        expect(await composer.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
      }
      async function chooseModel(name: string) {
        await modelMenu.click()
        await page.getByRole('option', { name: new RegExp(`^${name.replaceAll('.', '\\.')}`) }).click()
        await expect(modelMenu).toContainText(name)
      }
      await page.getByRole('button', { name: 'Denkaufwand: Standard', exact: true }).click()
      await expect(page.getByRole('menuitemcheckbox')).toHaveCount(3)
      await expect(page.getByRole('menuitemcheckbox', { name: /^(Sofort|Mittel|Pro) / })).toHaveCount(0)
      await page.keyboard.press('End')
      await page.keyboard.press('ArrowUp')
      await expect(page.getByRole('menuitemcheckbox', { name: /^Sehr hoch / })).toBeFocused()
      await page.keyboard.press('Enter')
      const reasoning = page.getByRole('button', { name: 'Denkaufwand: Sehr hoch', exact: true })
      await expect(reasoning).toBeVisible()
      const metrics = await reasoning.evaluate(element => {
        const label = element.querySelector('span:not([aria-hidden])')!
        const range = document.createRange()
        range.selectNodeContents(label)
        const rects = [...range.getClientRects()]
        const icon = element.querySelector('[data-slot="trailingIcon"]')!.getBoundingClientRect()
        const box = element.getBoundingClientRect()
        return { lines: new Set(rects.map(rect => rect.y)).size, textRight: Math.max(...rects.map(rect => rect.right)), iconLeft: icon.left, iconRight: icon.right, right: box.right, overflow: element.scrollWidth > element.clientWidth }
      })
      expect(metrics.lines).toBe(1)
      expect(metrics.textRight).toBeLessThanOrEqual(metrics.iconLeft)
      expect(metrics.iconRight).toBeLessThanOrEqual(metrics.right)
      expect(metrics.overflow).toBe(false)
      await geometry()
      await input.blur()
      await expect(page.locator('.composer-container')).toHaveScreenshot(`reasoning-${viewport.width}-${theme}-composer.png`, { animations: 'disabled', caret: 'hide' })
      await page.locator('.composer-container').screenshot({ path: resolve(`../docs/ui-reference/reasoning/after-${viewport.width}-${theme}.png`), animations: 'disabled' })
      await reasoning.click()
      await expect(page.getByRole('menuitemcheckbox', { name: /^Sehr hoch / })).toHaveAttribute('aria-checked', 'true')
      const rows = await page.getByRole('menuitemcheckbox').evaluateAll(elements => elements.map(element => {
        const label = element.querySelector('[data-slot="itemLabel"]')!.getBoundingClientRect()
        const description = element.querySelector('[data-slot="itemDescription"]')!.getBoundingClientRect()
        return { height: element.getBoundingClientRect().height, labelRight: label.right, descriptionLeft: description.left, labelOverflow: element.querySelector('[data-slot="itemLabel"]')!.scrollWidth > element.querySelector('[data-slot="itemLabel"]')!.clientWidth }
      }))
      expect(new Set(rows.map(row => row.height)).size).toBe(1)
      for (const row of rows) {
        expect(row.descriptionLeft).toBeGreaterThan(row.labelRight)
        expect(row.labelOverflow).toBe(false)
      }
      await expect(page.locator('.reasoning-menu')).toHaveScreenshot(`reasoning-${viewport.width}-${theme}-menu.png`, { animations: 'disabled' })
      await page.keyboard.press('Escape')
      await expect(page.locator('.reasoning-menu')).toBeHidden()
      await expect(reasoning).toBeFocused()
      await input.fill('Eine Frage\nmit Kontext\nund weiteren Zeilen\nfür das Modell')
      await expect.poll(async () => (await composer.boundingBox())!.height).toBeGreaterThan(initialComposer.height)
      await geometry()
      await input.press('Enter')
      await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
      async function lastCall(): Promise<ProviderCall> { return (await (await request.get(`${fixtureOrigin}/fixture/state`)).json()).calls.at(-1) }
      const glmCall = await lastCall()
      expect(glmCall.model).toBe(glm)
      expect(glmCall.chat_template_kwargs).toEqual({ reasoning_effort: 'max' })
      expect(glmCall.reasoning_effort).toBeUndefined()
      await input.fill('Eine Frage\nmit Kontext')
      await chooseModel('GPT-OSS 120B')
      await expect(page.getByRole('button', { name: 'Denkaufwand: Standard', exact: true })).toBeVisible()
      await geometry()
      await page.getByRole('button', { name: 'Denkaufwand: Standard', exact: true }).click()
      await expect(page.getByRole('menuitemcheckbox')).toHaveCount(4)
      await expect(page.getByRole('menuitemcheckbox', { name: /^(Sehr hoch|Pro) / })).toHaveCount(0)
      await page.getByRole('menuitemcheckbox', { name: /^Sofort / }).click()
      await input.press('Enter')
      await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
      expect((await lastCall()).reasoning_effort).toBe('low')
      expect((await lastCall()).chat_template_kwargs).toBeUndefined()
      await input.fill('Eine Frage\nmit Kontext')
      for (const name of otherModels) {
        await chooseModel(name)
        await expect(page.locator('.composer-reasoning')).toHaveCount(0)
        await geometry()
      }
      await input.press('Enter')
      await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
      expect((await lastCall()).reasoning_effort).toBeUndefined()
      expect((await lastCall()).chat_template_kwargs).toBeUndefined()
      await chooseModel('GLM 5.2')
      await expect(page.getByRole('button', { name: 'Denkaufwand: Standard', exact: true })).toBeVisible()
    })
  }
}
