import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

const fixtureOrigin = `http://127.0.0.1:${Number(process.env.NORIS_E2E_PROVIDER_PORT ?? 8591)}`
const draft = 'Erste Zeile\nMein Entwurf bleibt erhalten'
const uploadFile = { name: 'menu-context.txt', mimeType: 'text/plain', buffer: Buffer.from('Synthetic attachment context.') }
// Keep locators valid while checking the owned trigger and editable draft.
const triggerFor = (page: Page) => page.getByRole('button', { name: 'Anhänge und Werkzeuge', exact: true, includeHidden: true })
const inputFor = (page: Page) => page.getByRole('textbox', { name: 'Nachricht', exact: true, includeHidden: true })
const uploadFor = (page: Page) => page.getByRole('menuitem', { name: /^Fotos und Dateien hinzufügen/ })
const buttonAppearance = (page: Page) => triggerFor(page).evaluate(element => {
  const style = getComputedStyle(element)
  const circle = getComputedStyle(element, '::before')
  return {
    background: style.backgroundColor, shadow: style.boxShadow, border: style.borderWidth,
    circle: circle.backgroundColor, width: circle.width, height: circle.height, radius: circle.borderRadius,
    active: style.getPropertyValue('--noris-active-background').trim(), hover: style.getPropertyValue('--noris-hover-background').trim(),
    duration: circle.transitionDuration, transform: style.transform,
  }
})

test.beforeEach(async ({ page, request }) => {
  await request.post(`${fixtureOrigin}/fixture/catalog`, { data: { ids: ['fixture-alpha', 'fixture-beta', 'fixture-long'] } })
  const response = await request.get('/api/v1/conversations', { params: { archived: true, limit: 100 } })
  expect(response.ok()).toBe(true)
  for (const conversation of (await response.json()).conversations) await request.delete(`/api/v1/conversations/${conversation.id}`)
  await request.put('/api/v1/chat/drafts/new', { data: { content: '' } })
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null, modelId: null } })
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await expect(page.locator('.composer-submit')).toBeDisabled()
})

test('click toggles, outside click and Escape dismiss without losing text or replacing the composer', async ({ page }) => {
  const input = inputFor(page)
  const trigger = triggerFor(page)
  const menu = page.locator('.composer-plus-menu')
  await input.fill(draft)
  await input.evaluate(element => { element.dataset.instance = 'original-plus-menu-composer' })
  const before = await page.locator('.chat-composer').boundingBox()
  const buttonBefore = await trigger.boundingBox()
  const iconBefore = await trigger.locator('[data-slot="leadingIcon"]').boundingBox()
  for (const close of ['toggle', 'outside', 'escape']) {
    await page.mouse.move(0, 0)
    await expect.poll(async () => (await buttonAppearance(page)).circle).toBe('rgba(0, 0, 0, 0)')
    await trigger.click()
    await expect(menu).toBeVisible()
    await expect(trigger).toHaveAttribute('aria-expanded', 'true')
    await expect(trigger).toHaveAttribute('data-state', 'open')
    await page.mouse.move(0, 0)
    await expect.poll(async () => (await buttonAppearance(page)).circle).not.toBe('rgba(0, 0, 0, 0)')
    expect(await trigger.boundingBox()).toEqual(buttonBefore)
    expect(await trigger.locator('[data-slot="leadingIcon"]').boundingBox()).toEqual(iconBefore)
    expect(await page.locator('.chat-composer').boundingBox()).toEqual(before)
    if (close === 'toggle') await trigger.click()
    else if (close === 'outside') await page.mouse.click(2, 2)
    else await page.keyboard.press('Escape')
    await expect(menu).toBeHidden()
    await expect(trigger).toHaveAttribute('aria-expanded', 'false')
    await expect(trigger).toHaveAttribute('data-state', 'closed')
    await expect(trigger).toBeFocused()
    await expect(input).toHaveValue(draft)
    await expect(input).toHaveAttribute('data-instance', 'original-plus-menu-composer')
  }
  await page.mouse.move(0, 0)
  await expect.poll(async () => (await buttonAppearance(page)).circle).toBe('rgba(0, 0, 0, 0)')
})

test('delayed action-menu focus return preserves a newly opened model picker', async ({ page }) => {
  // Keep the native closing animation active while the next control opens.
  await page.addStyleTag({ content: '.composer-action-menu[data-state="closed"] { animation-duration: 800ms !important; }' })
  await inputFor(page).fill(draft)
  await triggerFor(page).click()
  const chooser = page.waitForEvent('filechooser')
  await uploadFor(page).click()
  await (await chooser).setFiles(uploadFile)
  const model = page.getByRole('button', { name: 'Modell im Eingabefeld auswählen', exact: true })
  await model.click()
  await expect(page.getByRole('listbox')).toBeVisible()
  await expect(page.locator('.composer-action-menu')).toHaveCount(0)
  await expect(model).toHaveAttribute('aria-expanded', 'true')
  await expect(inputFor(page)).not.toBeFocused()
  await page.getByRole('option', { name: 'Fixture Beta' }).click()
  await expect(model).toContainText('Fixture Beta')
  await expect(inputFor(page)).toHaveValue(draft)
  await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(1)
})

test('keyboard opening and arrow navigation skip unavailable actions; Enter and Space use the native multiple chooser', async ({ page }) => {
  const trigger = triggerFor(page)
  const menu = page.locator('.composer-plus-menu')
  await inputFor(page).fill(draft)
  for (const key of ['Enter', 'Space', 'ArrowDown']) {
    await trigger.focus()
    await trigger.press(key)
    await expect(menu).toBeVisible()
    await expect(uploadFor(page)).toBeFocused()
    for (const [arrow, learning] of [['ArrowDown', true], ['ArrowUp', false], ['Home', false], ['End', true]] as const) {
      await page.keyboard.press(arrow)
      await expect(learning ? page.getByRole('menuitem', { name: /^Lernen/ }) : uploadFor(page)).toBeFocused()
    }
    await page.keyboard.press('Escape')
    await expect(trigger).toBeFocused()
  }
  for (const key of ['Enter', 'Space']) {
    await trigger.press('Enter')
    const chooser = page.waitForEvent('filechooser')
    await uploadFor(page).press(key)
    expect((await chooser).isMultiple()).toBe(true)
    await (await chooser).setFiles([])
    await expect(menu).toBeHidden()
    await expect(trigger).toHaveAttribute('data-state', 'closed')
    await expect(inputFor(page)).toBeFocused()
    await expect(inputFor(page)).toHaveValue(draft)
  }
})

test('unimplemented tools are visibly disabled and cannot select or send the draft', async ({ page }) => {
  await inputFor(page).fill(draft)
  await triggerFor(page).click()
  const menu = page.locator('.composer-plus-menu')
  await expect(menu.getByRole('menuitem')).toHaveCount(7)
  for (const label of ['Aus Bibliothek hinzufügen', 'Bild erstellen', 'Websuche', 'Deep Research', 'Skizzieren']) {
    const item = menu.getByRole('menuitem', { name: new RegExp(`^${label}`) })
    await expect(item).toHaveAttribute('aria-disabled', 'true')
    await expect(item).not.toContainText('Noch nicht verfügbar')
    await item.click({ force: true })
    await expect(menu).toBeVisible()
  }
  await page.keyboard.press('Escape')
  await expect(inputFor(page)).toHaveValue(draft)
  await expect(page.locator('.message-user')).toHaveCount(0)
})

test('upload uses existing progress, previews, MIME validation and errors and restores composer focus', async ({ page }) => {
  let release!: () => void
  const held = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/v1/chat/attachments?*', async route => {
    if (route.request().method() === 'POST') await held
    await route.continue()
  })
  const input = inputFor(page)
  const creation = page.waitForResponse(response => response.url().endsWith('/api/v1/conversations') && response.request().method() === 'POST')
  await input.fill(draft)
  await triggerFor(page).click()
  const chooser = page.waitForEvent('filechooser')
  await uploadFor(page).click()
  await (await chooser).setFiles([uploadFile, { ...uploadFile, name: 'menu-notes.md', mimeType: 'text/markdown' }])
  expect((await creation).status()).toBe(201)
  await expect(page.locator('.composer-plus-menu')).toBeHidden()
  await expect(triggerFor(page)).toHaveAttribute('data-state', 'closed')
  await expect(input).toBeFocused()
  await expect(page.locator('[data-upload-status="uploading"]')).toHaveCount(2)
  await expect(page.getByRole('progressbar', { name: 'Uploadfortschritt: menu-context.txt' })).toBeVisible()
  release()
  await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(2)
  await triggerFor(page).click()
  const invalidChooser = page.waitForEvent('filechooser')
  await uploadFor(page).click()
  await (await invalidChooser).setFiles([{ name: 'unsupported.zip', mimeType: 'application/zip', buffer: Buffer.from('Synthetic invalid type') }])
  await expect(page.locator('[data-upload-status="failed"]')).toContainText('Dieser Dateityp wird nicht unterstützt.')
  await expect(input).toHaveValue(draft)
  await expect(input).toBeFocused()
  await page.reload()
  await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(2)
  await expect(input).toHaveValue(draft)
})

test('a saved conversation accepts another upload and removal preserves existing attachments and draft', async ({ page, request }) => {
  await inputFor(page).fill('Synthetische Frage')
  await inputFor(page).press('Enter')
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  const before = (await (await request.get('/api/v1/conversations')).json()).conversations
  expect(before).toHaveLength(1)
  await inputFor(page).fill(draft)
  for (const filename of ['existing-context.txt', 'existing-notes.txt']) {
    await triggerFor(page).click()
    const chooser = page.waitForEvent('filechooser')
    await uploadFor(page).click()
    await (await chooser).setFiles([{ ...uploadFile, name: filename }])
    await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(filename === 'existing-context.txt' ? 1 : 2)
  }
  const after = (await (await request.get('/api/v1/conversations')).json()).conversations
  expect(after.map((value: { id: string }) => value.id)).toEqual(before.map((value: { id: string }) => value.id))
  await page.getByRole('button', { name: 'existing-context.txt entfernen', exact: true }).click()
  await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(1)
  await expect(page.locator('.attachment-list')).toContainText('existing-notes.txt')
  await expect(inputFor(page)).toHaveValue(draft)
  await expect(inputFor(page)).toBeFocused()
  await expect(page.locator('.message-user')).toHaveCount(1)
})

test('a failed active-path request retains the real backend error and disables upload honestly', async ({ page }) => {
  await inputFor(page).fill('Synthetische Frage')
  await inputFor(page).press('Enter')
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  await page.route('**/api/v1/conversations/*/active-path?*', route => route.fulfill({
    status: 500, contentType: 'application/json',
    body: JSON.stringify({ error: { code: 'INTERNAL_ERROR', message: 'An internal error occurred', request_id: '00000000-0000-0000-0000-000000000001' } }),
  }))
  await page.reload()
  await expect(page.getByRole('main', { name: 'Chat', exact: true }).getByRole('alert').filter({ hasText: 'An internal error occurred' })).toBeVisible()
  await triggerFor(page).click()
  await expect(uploadFor(page)).toHaveAttribute('aria-disabled', 'true')
  await expect(uploadFor(page)).toContainText('An internal error occurred')
  await expect(page.locator('.composer-plus-menu')).not.toContainText('gespeicherte WebSocket-Unterhaltung')
  await page.keyboard.press('Escape')
  await expect(triggerFor(page)).toHaveAttribute('data-state', 'closed')
})

for (const width of [1440, 1700, 768, 390]) {
  for (const theme of ['light', 'dark']) {
    test(`plus menu position and screenshot ${width} ${theme}`, async ({ page, request }, info) => {
      test.skip(info.project.name !== 'desktop', 'Screenshot matrix runs once; interaction tests also run with touch emulation.')
      await page.setViewportSize({ width, height: width === 390 ? 844 : width === 768 ? 1024 : 900 })
      await page.evaluate(value => localStorage.setItem('noris-ai-theme', value), theme)
      await page.reload()
      await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      // Anchor to the dock, as in an ongoing chat, with synthetic fixture content.
      await inputFor(page).fill('Synthetische Frage')
      await inputFor(page).press('Enter')
      await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
      await expect.poll(async () => (await (await request.get('/api/v1/conversations')).json()).conversations[0]?.title).toBe('Docker DNS-Probleme')
      if (width >= 1024) await expect(page.getByRole('button', { name: 'Docker DNS-Probleme', exact: true })).toBeVisible()
      await inputFor(page).fill('Mein Entwurf')
      // The title commits independently after the answer. Capture the completed
      // metadata and ready composer together.
      await expect(page.locator('[data-conversation-id] button').first()).toHaveAttribute('title', 'Docker DNS-Probleme')
      await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
      const composer = page.locator('.chat-composer')
      const before = (await composer.boundingBox())!
      const trigger = triggerFor(page)
      const anchor = (await trigger.boundingBox())!
      const iconBefore = await trigger.locator('[data-slot="leadingIcon"]').boundingBox()
      await page.mouse.move(0, 0)
      await expect.poll(async () => (await buttonAppearance(page)).circle).toBe('rgba(0, 0, 0, 0)')
      await expect(page).toHaveScreenshot(`plus-button-closed-${width}-${theme}.png`, { animations: 'disabled', caret: 'hide' })
      await trigger.click()
      const menu = page.locator('.composer-plus-menu')
      await expect(menu).toBeVisible()
      await menu.evaluate(element => Promise.all(element.getAnimations().map(animation => animation.finished)))
      await page.mouse.move(0, 0)
      await expect.poll(async () => (await buttonAppearance(page)).circle).toBe(theme === 'light' ? 'rgb(239, 239, 239)' : 'rgb(43, 43, 43)')
      expect(await buttonAppearance(page)).toMatchObject({ background: 'rgba(0, 0, 0, 0)', shadow: 'none', border: '0px', width: '44px', height: '44px', radius: '50%', transform: 'none' })
      expect(await trigger.boundingBox()).toEqual(anchor)
      expect(await trigger.locator('[data-slot="leadingIcon"]').boundingBox()).toEqual(iconBefore)
      await expect(menu.locator('[data-slot="itemLeadingIcon"]')).toHaveCount(7)
      expect(await menu.locator('[data-slot="itemLeadingIcon"]').evaluateAll(elements => elements.every(element => {
        const style = getComputedStyle(element)
        return style.maskImage !== 'none' || style.backgroundImage !== 'none'
      }))).toBe(true)
      await expect(menu).toHaveAttribute('data-side', 'top')
      const box = (await menu.boundingBox())!
      expect(box.x).toBeGreaterThanOrEqual(12)
      expect(box.x + box.width).toBeLessThanOrEqual(width - 12)
      expect(box.y).toBeGreaterThanOrEqual(12)
      expect(box.y + box.height).toBeLessThanOrEqual(before.y - 7)
      if (width >= 640) {
        expect(box.x).toBeCloseTo(before.x, 0)
        expect(box.width).toBeCloseTo(before.width, 0)
        const copy = await uploadFor(page).evaluate(element => {
          const title = element.querySelector('[data-slot="itemLabel"]')!.getBoundingClientRect()
          const description = element.querySelector('[data-slot="itemDescription"]')!.getBoundingClientRect()
          return { titleTop: title.top, descriptionTop: description.top, titleRight: title.right, descriptionLeft: description.left }
        })
        expect(Math.abs(copy.titleTop - copy.descriptionTop)).toBeLessThan(5)
        expect(copy.descriptionLeft).toBeGreaterThan(copy.titleRight)
      }
      const heights = await menu.getByRole('menuitem').evaluateAll(elements => elements.map(element => element.getBoundingClientRect().height))
      if (width >= 640) expect(Math.max(...heights) - Math.min(...heights)).toBeLessThan(0.5)
      expect(Math.min(...heights)).toBeGreaterThanOrEqual(width === 390 ? 56 : 48)
      expect(await composer.boundingBox()).toEqual(before)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      await expect(page).toHaveScreenshot(`plus-menu-${width}-${theme}.png`, { animations: 'disabled', caret: 'hide' })
      await page.keyboard.press('Escape')
      await inputFor(page).fill(draft)
      const expanded = (await composer.boundingBox())!
      await trigger.click()
      await menu.evaluate(element => Promise.all(element.getAnimations().map(animation => animation.finished)))
      const expandedMenu = (await menu.boundingBox())!
      expect(expandedMenu.y + expandedMenu.height).toBeLessThanOrEqual(expanded.y - 7)
      await expect(inputFor(page)).toHaveValue(draft)
    })
  }
}

test('plus button has a subtle hover, visible keyboard focus and respects reduced motion', async ({ page }) => {
  const trigger = triggerFor(page)
  await trigger.hover()
  await expect.poll(async () => (await buttonAppearance(page)).circle).toBe('rgb(239, 239, 239)')
  expect((await buttonAppearance(page)).duration).toBe('0.1s')
  await page.mouse.move(0, 0)
  await inputFor(page).focus()
  await page.keyboard.press('Tab')
  await expect(trigger).toBeFocused()
  expect(await trigger.evaluate(element => {
    const style = getComputedStyle(element)
    return { visible: element.matches(':focus-visible'), width: style.outlineWidth, style: style.outlineStyle }
  })).toEqual({ visible: true, width: '2px', style: 'solid' })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  expect(parseFloat((await buttonAppearance(page)).duration)).toBeLessThan(0.001)
  await trigger.press('Enter')
  await expect(trigger).toHaveAttribute('aria-expanded', 'true')
  await page.keyboard.press('Escape')
  await expect(trigger).toHaveAttribute('aria-expanded', 'false')
})

test('the open menu repositions and scrolls within the keyboard viewport without covering the composer', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await inputFor(page).fill(draft)
  await triggerFor(page).click()
  const menu = page.locator('.composer-plus-menu')
  await expect(menu).toBeVisible()
  await page.evaluate(() => {
    Object.defineProperty(visualViewport!, 'height', { configurable: true, value: 300 })
    visualViewport!.dispatchEvent(new Event('resize'))
  })
  // Popper aligns to device pixels, yielding fractional CSS pixels on mobile.
  await expect.poll(async () => Math.round((await menu.boundingBox())!.y)).toBeGreaterThanOrEqual(12)
  await expect.poll(async () => {
    const box = (await menu.boundingBox())!
    return box.y + box.height - (await page.locator('.chat-composer').boundingBox())!.y
  }).toBeLessThanOrEqual(0)
  await expect.poll(async () => {
    const composer = (await page.locator('.chat-composer').boundingBox())!
    return composer.y + composer.height
  }).toBeLessThanOrEqual(300)
  expect(await menu.locator('[data-slot="viewport"]').evaluate(element => element.scrollHeight > element.clientHeight)).toBe(true)
  await page.keyboard.press('Escape')
  await expect(triggerFor(page)).toBeFocused()
  await expect(inputFor(page)).toHaveValue(draft)
})
