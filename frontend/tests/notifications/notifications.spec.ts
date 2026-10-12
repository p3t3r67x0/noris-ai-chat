import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import type { AppNotifications } from '../../app/composables/useAppNotifications'
import { notificationBackend } from './fixtures'

async function ready(page: Page) {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await expect(page.getByRole('textbox', { name: 'Nachricht', exact: true })).toBeEnabled()
  await expect(page.locator('.message-assistant').first()).toBeVisible()
}
async function send(page: Page) {
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.fill('Bitte ergänze eine Antwort.')
  await input.press('Enter')
}
// Drive the production presentation API through Vue's existing provider for palette cases.
// There is no test route, query parameter or global debug API in the shipped application.
async function palette(page: Page, severities: Array<'success' | 'info' | 'warning'>) {
  await page.evaluate(values => {
    interface VNode { component?: { provides: Record<symbol, AppNotifications>, subTree: VNode }, children?: VNode[], suspense?: { activeBranch: VNode } }
    function find(node: VNode | undefined): AppNotifications | undefined {
      if (!node) return
      if (node.component) {
        const providers = node.component.provides
        for (let source = providers; source; source = Object.getPrototypeOf(source)) {
          const key = Object.getOwnPropertySymbols(source).find(key => key.description === 'app-notifications')
          if (key) return providers[key]
        }
        const result = find(node.component.subTree)
        if (result) return result
      }
      if (node.suspense) return find(node.suspense.activeBranch)
      if (Array.isArray(node.children)) for (const child of node.children) { const result = find(child); if (result) return result }
    }
    const root = document.getElementById('__nuxt') as HTMLElement & { _vnode: VNode }
    const notifications = find(root._vnode)
    if (!notifications) throw new Error('Missing notification provider')
    for (const severity of values) notifications.notify({ severity, title: { success: 'Einstellung gespeichert.', info: 'Entwurf wiederhergestellt.', warning: 'Nutzungslimit fast erreicht.' }[severity], ...(severity === 'info' ? { description: 'Du kannst an deinem bisherigen Entwurf weiterarbeiten.' } : {}) })
  }, severities)
}
async function closeToasts(page: Page) {
  while (await page.getByRole('button', { name: 'Benachrichtigung schließen' }).count()) await page.getByRole('button', { name: 'Benachrichtigung schließen' }).first().click()
}

for (const size of [{ width: 1700, height: 900 }, { width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  for (const theme of ['light', 'dark'] as const) {
    test(`presentation ${size.width} ${theme}`, async ({ page }) => {
      await page.setViewportSize(size)
      await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' })
      const state = await notificationBackend(page, { failUploads: 1 })
      await ready(page)
      const screenshot = async (name: string) => {
        await page.screenshot({ path: `../docs/notifications/screenshots/after/${size.width}-${theme}-${name}.png` })
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      }
      const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
      await input.focus()
      const dock = await page.locator('.chat-composer').boundingBox()
      for (const severity of ['success', 'info', 'warning'] as const) {
        await input.focus()
        await palette(page, [severity])
        await expect(page.locator('.app-notification')).toHaveCount(1)
        await expect(input).toBeFocused()
        await expect(page.locator('[data-notification-announcer=status]')).not.toBeEmpty()
        expect(await page.locator('.chat-composer').boundingBox()).toEqual(dock)
        await screenshot(severity)
        await closeToasts(page)
      }
      await palette(page, ['success', 'info', 'warning'])
      await expect(page.locator('.app-notification')).toHaveCount(3)
      await screenshot('multiple')
      const header = await page.locator('.chat-header').boundingBox()
      for (const toast of await page.locator('.app-notification').all()) {
        const box = (await toast.boundingBox())!
        expect(box.y).toBeGreaterThanOrEqual(header!.y + header!.height)
        expect(box.x).toBeGreaterThanOrEqual(0)
        expect(box.x + box.width).toBeLessThanOrEqual(size.width)
        expect(box.y + box.height).toBeLessThanOrEqual(size.height)
      }
      await closeToasts(page)
      await send(page)
      await expect(page.locator('.message-assistant').last()).toHaveAttribute('data-status', 'failed')
      await expect(page.locator('.app-notification')).toHaveCount(1)
      await expect(page.locator('.app-notification')).toContainText('Der Modelldienst ist momentan nicht erreichbar.')
      await expect(page.locator('.composer-dock')).not.toContainText('Der Modelldienst')
      await expect(page.locator('.chat-status')).not.toContainText('Der Modelldienst')
      await expect(page.locator('[data-notification-announcer=alert]')).toContainText('Antwort konnte nicht erstellt werden.')
      await expect(page.locator('.message-assistant').first()).toContainText('Dein bisheriger Chat bleibt erhalten.')
      expect(state.generations).toBe(1)
      await screenshot('error-retry')
      await screenshot('generation')
      await page.locator('.app-notification').getByRole('button', { name: 'Erneut versuchen', exact: true }).click()
      await expect(page.locator('.message-assistant').last()).toHaveAttribute('data-status', 'completed')
      await expect(page.locator('.message-assistant[data-status=failed]')).toHaveCount(0)
      expect(state.generations).toBe(2)
      await closeToasts(page)
      await page.locator('input[type=file]').first().setInputFiles({ name: 'beispiel.txt', mimeType: 'text/plain', buffer: Buffer.from('Beispieltext') })
      await expect(page.locator('[data-upload-status=failed]')).toContainText('Fehlgeschlagen')
      await expect(page.locator('[data-upload-status=failed]')).toContainText('Der Upload hat zu lange gedauert.')
      await screenshot('upload')
      await page.getByRole('button', { name: 'beispiel.txt erneut hochladen' }).click()
      await expect(page.locator('[data-upload-status=uploaded]')).toBeVisible()
      expect(state.uploads).toBe(2)
      await expect(page.locator('.app-notification')).toHaveCount(0)
    })
  }
}

test('keyboard, safe details, Escape and retry preserve partial text', async ({ page }) => {
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write'])
  const state = await notificationBackend(page)
  await ready(page)
  await send(page)
  await expect(page.locator('.app-notification')).toHaveCount(1)
  await expect(page.locator('.message-assistant').last()).toContainText('Diese Teilantwort bleibt')
  const details = page.locator('.app-notification').getByRole('button', { name: 'Details', exact: true })
  await details.focus()
  await page.keyboard.press('Enter')
  const dialog = page.getByRole('dialog', { name: 'Fehlerdetails' })
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText('PROVIDER_UNREACHABLE')
  await expect(dialog).toContainText('Generation-ID:')
  await expect(dialog).not.toContainText('DO_NOT_DISPLAY')
  await dialog.getByRole('button', { name: 'Diagnose kopieren' }).click()
  await expect(dialog.getByRole('button', { name: 'Kopiert', exact: true })).toBeVisible()
  const copied = await page.evaluate(() => navigator.clipboard.readText())
  expect(copied).toContain('Fehlercode: PROVIDER_UNREACHABLE')
  expect(copied).not.toContain('Bitte ergänze eine Antwort')
  await expect(page.locator('body')).not.toContainText('An internal error occurred')
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  expect(state.generations).toBe(1)
  // Recovery remains at the assistant message after dismissal / diagnostic inspection.
  const retry = page.locator('.message-assistant').last().getByRole('button', { name: 'Erneut versuchen', exact: true })
  await retry.focus()
  await page.keyboard.press('Enter')
  await expect(page.locator('.message-assistant').last()).toHaveAttribute('data-status', 'completed')
  expect(state.generations).toBe(2)
})

test('lifetimes, bounded queue, reduced motion and a resized keyboard viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await notificationBackend(page)
  await ready(page)
  await page.clock.install()
  await page.clock.pauseAt(new Date(await page.evaluate(() => Date.now()) + 100))
  await palette(page, ['success', 'info', 'warning', 'info', 'warning'])
  await page.clock.runFor(100)
  await expect(page.locator('.app-notification')).toHaveCount(3)
  await page.clock.runFor(3600)
  await expect(page.locator('.app-notification')).toHaveCount(3)
  await page.clock.runFor(12000)
  await expect(page.locator('.app-notification')).toHaveCount(0)
  await page.setViewportSize({ width: 390, height: 420 })
  await palette(page, ['warning'])
  await page.clock.runFor(100)
  await expect(page.locator('.app-notification')).toBeInViewport()
  expect(await page.locator('.app-notification').evaluate(element => getComputedStyle(element).animationName)).toBe('none')
  await page.locator('.app-notification').focus()
  await page.keyboard.press('Escape')
  await page.clock.runFor(250)
  await expect(page.locator('.app-notification')).toHaveCount(0)
})

for (const code of ['TIMEOUT', 'RATE_LIMIT', 'MODEL_UNAVAILABLE', 'NETWORK_ERROR']) {
  test(`generation ${code} has understandable recovery without a second request`, async ({ page }) => {
    const state = await notificationBackend(page, { generationCode: code, partial: '' })
    await ready(page)
    await send(page)
    await expect(page.locator('.app-notification')).toHaveCount(1)
    await expect(page.locator('.app-notification')).not.toContainText('An internal error occurred')
    await expect(page.locator('.message-assistant').last()).toHaveAttribute('data-status', 'failed')
    expect(state.generations).toBe(1)
  })
}

test('settings failure remains recoverable and saves only on explicit retry', async ({ page }) => {
  const state = await notificationBackend(page, { failSettings: 1 })
  await ready(page)
  await page.getByRole('button', { name: 'Anhänge und Werkzeuge', exact: true }).click()
  await page.getByRole('menuitem', { name: /Lernen/ }).click()
  await expect(page.locator('.app-notification')).toContainText('Einstellung konnte nicht gespeichert werden.')
  expect(state.settings).toBe(1)
  await page.locator('.app-notification').getByRole('button', { name: 'Erneut speichern' }).click()
  await expect(page.locator('.composer-container')).toHaveAttribute('data-mode', 'learning')
  expect(state.settings).toBe(2)
})

test('normal generation completes without a toast and preserves the previous conversation', async ({ page }) => {
  const state = await notificationBackend(page, { generationCode: '' })
  await ready(page)
  await send(page)
  await expect(page.locator('.message-assistant').last()).toHaveAttribute('data-status', 'completed')
  await expect(page.locator('.message-assistant').first()).toContainText('Dein bisheriger Chat bleibt erhalten.')
  await expect(page.locator('.app-notification')).toHaveCount(0)
  expect(state.generations).toBe(1)
})

test('WebSocket reconnect resumes the existing generation without a duplicate request or toast', async ({ page }) => {
  const state = await notificationBackend(page, { generationCode: '', disconnect: true })
  await ready(page)
  await send(page)
  await expect(page.locator('.message-assistant').last()).toHaveAttribute('data-status', 'completed', { timeout: 10000 })
  await expect(page.locator('.message-assistant').last()).toContainText('Die erneut angeforderte Antwort wurde erfolgreich erstellt.')
  expect(state.generations).toBe(1)
  expect(state.resumes).toBe(1)
  await expect(page.locator('.app-notification')).toHaveCount(0)
})

test('failed deletion keeps the chat, retries in the dialog and confirms successful deletion without Undo', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const state = await notificationBackend(page, { failDelete: 1 })
  await ready(page)
  await page.getByRole('button', { name: 'Aktionen für Benachrichtigungen prüfen' }).click()
  await page.getByRole('menuitem', { name: 'Löschen', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Chat löschen?' })
  await dialog.getByRole('button', { name: 'Chat löschen', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('Chat konnte nicht gelöscht werden.')
  expect(state.deletes).toBe(1)
  await expect(page.locator('.message-assistant').first()).toContainText('Dein bisheriger Chat bleibt erhalten.')
  await dialog.getByRole('button', { name: 'Chat löschen', exact: true }).click()
  await expect(dialog).toBeHidden()
  await expect(page.locator('.app-notification')).toContainText('Chat gelöscht.')
  await expect(page.locator('.app-notification')).not.toContainText('Undo')
  expect(state.deletes).toBe(2)
})
