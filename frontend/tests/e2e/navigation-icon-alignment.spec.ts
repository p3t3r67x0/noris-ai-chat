import { expect, test } from '@playwright/test'
import type { Locator, Page } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { savedChat, seedChat } from './chat-fixtures'

test.use({ deviceScaleFactor: 1 })
const phase = process.env.NORIS_UI_CAPTURE_PHASE ?? 'after'
const evidence = fileURLToPath(new URL(`../../../docs/navigation-icons/evidence/${phase}`, import.meta.url))

async function geometry(button: Locator) {
  return button.evaluate(async (element) => {
    const icon = element.querySelector<HTMLElement>('[data-slot="leadingIcon"]')!
    const button = element.getBoundingClientRect(), rect = icon.getBoundingClientRect()
    const css = getComputedStyle(icon)
    // Nuxt Icon renders a span with an SVG CSS mask, not an inline <svg>.
    // Rasterize that very mask, including its stroke, at 8x for visible bounds.
    const source = css.maskImage === 'none' ? css.backgroundImage : css.maskImage
    const url = source.match(/^url\(["']?(.*?)["']?\)$/)?.[1]
    let ink = null
    if (url) {
      const img = new Image()
      img.src = url
      await img.decode()
      const canvas = document.createElement('canvas')
      canvas.width = rect.width * 8; canvas.height = rect.height * 8
      const context = canvas.getContext('2d')!
      context.drawImage(img, 0, 0, canvas.width, canvas.height)
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data
      let left = canvas.width, right = 0, top = canvas.height, bottom = 0
      for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
        if (pixels[(y * canvas.width + x) * 4 + 3]! < 32) continue
        left = Math.min(left, x); right = Math.max(right, x + 1)
        top = Math.min(top, y); bottom = Math.max(bottom, y + 1)
      }
      ink = { deltaX: (left + right) / 16 - rect.width / 2, deltaY: (top + bottom) / 16 - rect.height / 2 }
    }
    return {
      button: button.toJSON(), icon: rect.toJSON(),
      deltaX: rect.x + rect.width / 2 - button.x - button.width / 2,
      deltaY: rect.y + rect.height / 2 - button.y - button.height / 2,
      radius: getComputedStyle(element).borderRadius, ink,
    }
  })
}

async function states(page: Page, button: Locator) {
  const result: Record<string, Awaited<ReturnType<typeof geometry>>> = {}
  await page.mouse.move(0, 400)
  result.default = await geometry(button)
  await button.hover(); result.hover = await geometry(button)
  await page.mouse.down(); result.active = await geometry(button)
  await page.mouse.move(0, 400); await page.mouse.up()
  await page.keyboard.press('Tab'); await button.focus()
  result.focus = await geometry(button)
  await button.evaluate(element => { (element as HTMLButtonElement).disabled = true })
  result.disabled = await geometry(button)
  await button.evaluate(element => { (element as HTMLButtonElement).disabled = false })
  if (phase !== 'before') for (const value of Object.values(result)) {
    expect(value.button.width).toBe(44); expect(value.button.height).toBe(44)
    expect(value.icon.width).toBe(20); expect(value.icon.height).toBe(20)
    expect(value.radius).toBe('12px')
    expect(Math.abs(value.deltaX)).toBeLessThanOrEqual(0.5)
    expect(Math.abs(value.deltaY)).toBeLessThanOrEqual(0.5)
    expect(value.ink).not.toBeNull()
    expect(Math.abs(value.ink!.deltaX)).toBeLessThanOrEqual(0.5)
    expect(Math.abs(value.ink!.deltaY)).toBeLessThanOrEqual(0.5)
    expect(value.button).toEqual(result.default!.button)
    expect(value.icon).toEqual(result.default!.icon)
  }
  return result
}

for (const [width, height] of [[1701, 863], [1440, 900], [390, 844]] as const) for (const theme of ['light', 'dark']) {
  test(`navigation icon geometry ${width} ${theme}`, async ({ page }, info) => {
    test.skip(info.project.name !== 'desktop', 'Explicit viewport and DPR matrix')
    await mkdir(evidence, { recursive: true })
    await page.setViewportSize({ width, height })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await seedChat(page, savedChat(), theme)
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    const measurements: Record<string, unknown> = {
      environment: await page.evaluate(() => ({ viewport: [innerWidth, innerHeight], dpr: devicePixelRatio, scale: visualViewport?.scale, userAgent: navigator.userAgent })),
    }
    const toggle = page.locator('.sidebar-heading button[aria-controls="chat-sidebar"]:visible')
    if (width < 1024) await page.locator('.chat-header button[aria-controls="chat-sidebar"]').click()
    await expect(toggle).toBeVisible()
    measurements.toggle = await states(page, toggle)
    if (width >= 1024) {
      measurements.search = await states(page, page.locator('.sidebar-heading button').first())
      measurements.railSearch = await states(page, page.locator('.chat-rail button').nth(1))
    }
    await toggle.hover()
    await page.screenshot({ path: resolve(evidence, `${width}-${theme}-open.png`) })
    await toggle.click()
    const newChat = page.locator('.chat-header').getByRole('button', { name: 'Neuer Chat', exact: true })
    await expect(newChat).toBeVisible()
    measurements.newChat = await states(page, newChat)
    if (width >= 1024) {
      measurements.reopen = await states(page, page.locator('.rail-sidebar-open'))
      await expect(page.locator('.chat-rail')).toBeVisible()
      await expect(page.locator('.chat-header button[aria-controls="chat-sidebar"]')).toBeHidden()
    } else measurements.mobileToggle = await states(page, page.locator('.chat-header button[aria-controls="chat-sidebar"]'))
    await expect(page.getByRole('button', { name: 'Neuer Chat', exact: true }).filter({ visible: true })).toHaveCount(1)
    await newChat.hover()
    await page.screenshot({ path: resolve(evidence, `${width}-${theme}-closed.png`) })
    await writeFile(resolve(evidence, `${width}-${theme}.json`), JSON.stringify(measurements, null, 2))
    if (phase === 'before') return
    if (width >= 1024) {
      await page.reload()
      await expect(page.locator('.rail-sidebar-open')).toBeVisible()
      await page.locator('.rail-sidebar-open').click()
      await expect(toggle).toBeVisible()
      await toggle.click()
    }
    await page.locator('.composer-input').fill('Entwurf behalten')
    await newChat.click()
    await expect(page.locator('.composer-input')).toBeFocused()
    await expect(page.locator('.composer-input')).toHaveValue('')
    await page.keyboard.press('Control+k')
    await expect(page.locator('#chat-search-input')).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(page.locator('.composer-input')).toBeFocused()
  })
}
