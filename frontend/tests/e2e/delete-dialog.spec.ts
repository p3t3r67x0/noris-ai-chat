import { expect, test, type Page } from '@playwright/test'
import { savedChat, seedChat } from './chat-fixtures'
import { CHAT_STORAGE_KEY } from '../../app/lib/chat/persistence'

const title = 'Synthetische Statusübersicht'
const keepTitle = 'Synthetischer Projektplan'

async function start(page: Page, theme = 'light', targetTitle = title) {
  const snapshot = savedChat()
  snapshot.conversations.conversations = Object.fromEntries(Object.entries(snapshot.conversations.conversations).filter(([id]) => ['main', 'conversation-1'].includes(id)))
  snapshot.conversations.conversations.main!.title = targetTitle
  snapshot.conversations.conversations['conversation-1']!.title = keepTitle
  snapshot.drafts.main = 'Synthetischer Entwurf bleibt erhalten'
  snapshot.drafts['conversation-1'] = 'Unabhängiger Entwurf'
  await seedChat(page, snapshot, theme)
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  return snapshot
}

async function openDelete(page: Page, targetTitle = title, keyboard = false) {
  const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  const trigger = page.getByRole('button', { name: `Aktionen für ${targetTitle}`, exact: true })
  if (keyboard) { await trigger.focus(); await trigger.press('Enter') }
  else await trigger.click()
  await page.getByRole('menuitem', { name: 'Löschen', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Chat löschen?', exact: true })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Abbrechen', exact: true })).toBeFocused()
  await expect(page.getByRole('menu')).toHaveCount(0)
  return dialog
}

async function snapshot(page: Page) {
  return page.evaluate(key => JSON.parse(localStorage.getItem(key)!), CHAT_STORAGE_KEY)
}

for (const theme of ['light', 'dark']) {
  test(`delete dialog geometry, overlay, keyboard and screenshot ${theme}`, async ({ page }, testInfo) => {
    const mobile = testInfo.project.name === 'mobile'
    const viewport = mobile ? { width: 390, height: 844 } : { width: 1701, height: 863 }
    await page.setViewportSize(viewport)
    await start(page, theme)
    const dialog = await openDelete(page, title, true)
    await expect(dialog).toHaveAttribute('aria-modal', 'true')
    await expect(dialog).toHaveAccessibleDescription(`Dadurch wird ${title} endgültig gelöscht. Dieser Vorgang kann nicht rückgängig gemacht werden.`)
    const box = (await dialog.boundingBox())!
    expect(box.width).toBe(mobile ? 358 : 485)
    expect(Math.abs(box.x + box.width / 2 - viewport.width / 2)).toBeLessThanOrEqual(1)
    expect(Math.abs(box.y + box.height / 2 - viewport.height / 2)).toBeLessThanOrEqual(1)
    expect(box.height).toBeLessThan(320)
    const overlay = page.locator('.delete-dialog-overlay')
    expect(await overlay.boundingBox()).toEqual({ x: 0, y: 0, ...viewport })
    const style = await dialog.evaluate(element => {
      const s = getComputedStyle(element)
      const overlay = document.querySelector('.delete-dialog-overlay')!
      const os = getComputedStyle(overlay)
      return { radius: s.borderRadius, padding: s.padding, border: s.borderWidth, blur: os.backdropFilter, layer: Number(s.zIndex) > Number(os.zIndex), descriptionFont: getComputedStyle(element.querySelector('[data-slot="description"]')!).fontSize }
    })
    expect(style).toEqual({ radius: '26px', padding: '24px', border: '0px', blur: 'none', layer: true, descriptionFont: '18px' })
    const appearance = await dialog.evaluate(element => {
      const color = (selector: string) => {
        const s = getComputedStyle(element.querySelector(selector)!)
        return { text: s.color, background: s.backgroundColor }
      }
      return {
        surface: getComputedStyle(element).backgroundColor,
        cancel: color('.delete-dialog-cancel'), confirm: color('.delete-dialog-confirm'),
        cornersCovered: [[4, 4], [innerWidth - 4, 4], [4, innerHeight - 4], [innerWidth - 4, innerHeight - 4]].every(([x, y]) => document.elementFromPoint(x!, y!)?.classList.contains('delete-dialog-overlay')),
      }
    })
    expect(appearance.cornersCovered).toBe(true)
    expect(appearance.surface).toBe(theme === 'light' ? 'rgb(255, 255, 255)' : 'rgb(48, 48, 48)')
    expect(appearance.confirm).toEqual(theme === 'light'
      ? { text: 'rgb(197, 34, 34)', background: 'rgb(252, 232, 232)' }
      : { text: 'rgb(255, 170, 170)', background: 'rgb(81, 44, 44)' })
    const close = dialog.getByRole('button', { name: 'Dialog schließen', exact: true })
    const cancel = dialog.getByRole('button', { name: 'Abbrechen', exact: true })
    const remove = dialog.getByRole('button', { name: 'Chat löschen', exact: true })
    await page.keyboard.press('Tab'); await expect(remove).toBeFocused()
    await page.keyboard.press('Tab'); await expect(close).toBeFocused()
    await page.keyboard.press('Shift+Tab'); await expect(remove).toBeFocused()
    await page.keyboard.press('Shift+Tab'); await expect(cancel).toBeFocused()
    await expect(page).toHaveScreenshot(`delete-dialog-${theme}.png`, { animations: 'disabled' })
    await testInfo.attach('dialog-measurements', { body: JSON.stringify({ viewport, box, style, appearance }), contentType: 'application/json' })
    await page.keyboard.press('Escape')
    await expect(dialog).not.toBeVisible()
    if (mobile) await expect(page.locator('#chat-main')).toBeFocused()
    else await expect(page.getByRole('button', { name: `Aktionen für ${title}`, exact: true })).toBeFocused()
    await expect(page.getByRole('textbox', { name: 'Nachricht', exact: true })).toHaveValue('Synthetischer Entwurf bleibt erhalten')
    expect((await snapshot(page)).conversations.activeConversationId).toBe('main')
  })
}

for (const action of ['Abbrechen', 'Dialog schließen', 'Enter', 'outside']) {
  test(`cancel via ${action} preserves conversations, messages and drafts`, async ({ page }) => {
    const before = await start(page)
    const dialog = await openDelete(page)
    await page.keyboard.press('Control+Shift+o')
    await page.keyboard.press('Control+k')
    await expect(page.getByRole('dialog')).toHaveCount(1)
    await expect(dialog.getByRole('button', { name: 'Abbrechen', exact: true })).toBeFocused()
    if (action === 'Enter') await page.keyboard.press('Enter')
    else if (action === 'outside') await page.mouse.click(4, 4)
    else await dialog.getByRole('button', { name: action, exact: true }).click()
    await expect(dialog).not.toBeVisible()
    expect(await snapshot(page)).toEqual(before)
  })
}

for (const active of [true, false]) {
  test(`confirmed deletion preserves a valid conversation state, active: ${active}`, async ({ page }) => {
    const before = await start(page)
    const dialog = await openDelete(page, active ? title : keepTitle)
    await dialog.getByRole('button', { name: 'Chat löschen', exact: true }).focus()
    await page.keyboard.press('Enter')
    await expect(dialog).not.toBeVisible()
    const removedId = active ? 'main' : 'conversation-1'
    await expect.poll(async () => Object.hasOwn((await snapshot(page)).conversations.conversations, removedId)).toBe(false)
    const after = await snapshot(page)
    expect(after.conversations.activeConversationId).toBe(active ? null : 'main')
    const retainedId = active ? 'conversation-1' : 'main'
    expect(after.conversations.conversations[retainedId]).toEqual(before.conversations.conversations[retainedId])
    expect(after.drafts[retainedId]).toBe(before.drafts[retainedId])
    expect(after.drafts[removedId]).toBeUndefined()
    expect(Object.values(after.messages).every(message => (message as { conversationId: string }).conversationId !== removedId)).toBe(true)
    await page.reload()
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    expect((await snapshot(page)).conversations.activeConversationId).toBe(active ? null : 'main')
  })
}

test('long untrusted titles wrap within the mobile dialog without rendering HTML', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 })
  const longTitle = '<img src=x onerror=alert(1)>' + 'A'.repeat(92)
  await start(page, 'light', longTitle)
  const dialog = await openDelete(page, longTitle)
  await expect(dialog.locator('img')).toHaveCount(0)
  await expect(dialog).toContainText(longTitle)
  expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth && document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  const buttons = dialog.locator('.delete-dialog-button')
  for (const button of await buttons.all()) await expect(button).toBeInViewport()
  await page.keyboard.press('Escape')
})
