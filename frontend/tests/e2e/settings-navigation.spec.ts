import { expect, test } from '@playwright/test'
import { savedChat, seedChat } from './chat-fixtures'
import { openSettingsCategory, returnToChat } from './settings-helpers'

async function navigation(page: import('@playwright/test').Page) {
  const toggle = page.getByRole('button', { name: /^(Einstellungsnavigation|Settings navigation)$/ })
  if (await toggle.isVisible() && await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  return page.locator('.settings-sidebar')
}

test('direct routes, redirect, browser history and active navigation', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => { if (/hydration/i.test(message.text())) errors.push(message.text()) })
  await page.goto('/settings')
  await expect(page).toHaveURL(/\/settings\/general$/)
  await expect(page.getByRole('heading', { name: 'Allgemein', exact: true })).toBeVisible()
  await expect((await navigation(page)).getByRole('link', { name: 'Allgemein', exact: true })).toHaveAttribute('aria-current', 'page')
  await openSettingsCategory(page, 'Darstellung')
  await expect(page.getByRole('heading', { name: 'Darstellung', exact: true, level: 1 })).toBeFocused()
  await page.goBack()
  await expect(page).toHaveURL(/\/settings\/general$/)
  await page.goForward()
  await expect(page).toHaveURL(/\/settings\/appearance$/)
  for (const [path, label] of [['archived', 'Archivierte Chats'], ['models', 'Modelle'], ['keyboard', 'Tastatur'], ['data-controls', 'Datenkontrollen']] as const) {
    await page.goto(`/settings/${path}`)
    await expect(page.getByRole('heading', { name: label, exact: true })).toBeVisible()
  }
  expect(errors).toEqual([])
})

test('local search opens and focuses a setting and hides unsupported actions', async ({ page }) => {
  let requests = 0
  page.on('request', request => { if (request.url().includes('/api/')) requests++ })
  await page.goto('/settings/general')
  const sidebar = await navigation(page)
  const input = sidebar.getByRole('textbox', { name: 'Einstellungen durchsuchen' })
  await input.fill('Dark Mode')
  const before = requests
  await expect(sidebar.getByRole('link', { name: /Darstellung/ })).toBeVisible()
  await input.press('Enter')
  await expect(page).toHaveURL(/\/settings\/appearance#theme$/)
  await expect(page.getByRole('combobox', { name: 'Darstellung Einstellungen' })).toBeFocused()
  expect(requests).toBe(before)
  await navigation(page)
  await input.fill('Importieren')
  await expect(sidebar.getByRole('status')).toHaveText('Keine passenden Einstellungen.')
  await input.fill('Reasoning')
  await sidebar.getByRole('link', { name: /noris Reasoning/ }).click()
  await expect(page.locator('#model-reasoning')).toBeFocused()
  await navigation(page)
  await input.fill('unbekannte funktion')
  await expect(sidebar.getByRole('status')).toHaveText('Keine passenden Einstellungen.')
})

test('language changes visible settings and chat controls, persists and detects the browser', async ({ page }) => {
  await page.goto('/settings/general')
  await page.getByRole('combobox', { name: 'Sprache', exact: true }).click()
  await page.getByRole('option', { name: 'English', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'General', exact: true })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  await page.reload()
  await expect(page.getByRole('combobox', { name: 'Language', exact: true })).toContainText('English')
  await navigation(page)
  await page.getByRole('link', { name: 'Back to chat' }).click()
  await expect(page.getByRole('textbox', { name: 'Message', exact: true })).toHaveAttribute('placeholder', 'Ask noris AI …')
  await expect(page.getByRole('heading', { name: 'What would you like to work on today?' })).toBeVisible()
  await page.goto('/settings/general')
  await page.getByRole('combobox', { name: 'Language', exact: true }).click()
  await page.getByRole('option', { name: 'Detect automatically' }).click()
  await expect(page.getByRole('heading', { name: 'Allgemein', exact: true })).toBeVisible()
})

test('theme applies immediately, persists and follows system changes', async ({ page }) => {
  await page.goto('/settings/appearance')
  const select = page.getByRole('combobox', { name: 'Darstellung Einstellungen' })
  await select.click()
  await page.getByRole('option', { name: 'Dunkel', exact: true }).click()
  await expect(page.locator('html')).toHaveClass(/dark/)
  await page.reload()
  await expect(page.locator('html')).toHaveClass(/dark/)
  await select.click()
  await page.getByRole('option', { name: 'Hell', exact: true }).click()
  await expect(page.locator('html')).toHaveClass(/light/)
  await select.click()
  await page.getByRole('option', { name: 'System', exact: true }).click()
  await page.emulateMedia({ colorScheme: 'dark' })
  await expect(page.locator('html')).toHaveClass(/dark/)
  await page.emulateMedia({ colorScheme: 'light' })
  await expect(page.locator('html')).toHaveClass(/light/)
})

test('model preference shares the composer state and survives reload', async ({ page }) => {
  await page.goto('/settings/models')
  await page.getByRole('combobox', { name: 'Standardmodell' }).click()
  await page.getByRole('option', { name: 'noris Fast', exact: true }).click()
  await returnToChat(page)
  await expect(page.getByRole('button', { name: 'Modell im Eingabefeld auswählen' })).toContainText('Fast')
  await page.reload()
  await expect(page.getByRole('button', { name: 'Modell auswählen', exact: true })).toContainText('noris Fast')
})

test('archived chats reuse restore and the delete confirmation', async ({ page }) => {
  const snapshot = savedChat()
  snapshot.conversations.conversations['conversation-1']!.archivedAt = '2026-10-09T12:00:00Z'
  snapshot.conversations.conversations['conversation-2']!.archivedAt = '2026-10-09T12:00:00Z'
  await seedChat(page, snapshot)
  await page.goto('/settings/archived')
  await page.getByRole('button', { name: 'Gedanken 1 wiederherstellen' }).click()
  await expect(page.getByRole('button', { name: 'Gedanken 1 wiederherstellen' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Gedanken 2 löschen' }).click()
  const dialog = page.getByRole('dialog', { name: 'Chat löschen?' })
  await expect(dialog.getByRole('button', { name: 'Abbrechen' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'Gedanken 2 löschen' })).toBeFocused()
  await page.getByRole('button', { name: 'Gedanken 2 löschen' }).click()
  await dialog.getByRole('button', { name: 'Chat löschen', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Archivierte Chats', exact: true })).toBeFocused()
  await returnToChat(page)
  await page.reload()
  const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  await expect(page.getByRole('navigation', { name: 'Gespräche' }).getByRole('button', { name: 'Gedanken 1', exact: true })).toBeVisible()
  await expect(page.locator('[data-conversation-id="conversation-2"]')).toHaveCount(0)
})

test('generation continues while settings replace the chat view', async ({ page }) => {
  await page.goto('/')
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.fill('/lang')
  await input.press('Enter')
  await expect(page.locator('[data-generation-status]')).toHaveAttribute('data-generation-status', 'streaming')
  const firstLength = await page.locator('.message-assistant').innerText()
  await input.fill('Synthetischer Entwurf')
  await input.evaluate(element => { element.dataset.instance = 'retained' })
  const rail = page.locator('.chat-rail')
  if (await rail.isVisible()) {
    await rail.getByRole('button', { name: 'Lokaler Arbeitsbereich' }).click()
    await page.getByRole('menuitem', { name: 'Einstellungen', exact: true }).click()
  }
  else {
    await page.getByRole('button', { name: 'Sidebar öffnen', exact: true }).click()
    await page.getByRole('button', { name: 'Einstellungen', exact: true }).click()
  }
  await expect(page.getByRole('main', { name: 'Einstellungen' })).toBeVisible()
  await expect.poll(async () => (await page.locator('.message-assistant').innerText()).length).toBeGreaterThan(firstLength.length)
  await returnToChat(page)
  await expect(input).toHaveAttribute('data-instance', 'retained')
  await expect(input).toHaveValue('Synthetischer Entwurf')
  await expect(page.getByRole('button', { name: 'Antwort stoppen', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Antwort stoppen', exact: true }).click()
})

for (const theme of ['light', 'dark']) test(`settings visual baseline ${theme}`, async ({ page }, testInfo) => {
  if (testInfo.project.name === 'desktop') await page.setViewportSize({ width: 1920, height: 975 })
  await page.addInitScript(theme => localStorage.setItem('noris-ai-theme', theme), theme)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/settings/general')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await expect(page.getByRole('combobox', { name: 'Sprache', exact: true })).toContainText('Automatisch erkennen')
  await page.getByRole('heading', { name: 'Allgemein', exact: true }).evaluate(element => (element as HTMLElement).blur())
  await expect(page).toHaveScreenshot(`settings-general-${theme}.png`, { animations: 'disabled' })
})

test('reference proportions and every requested viewport fit without overflow', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Explicit viewport matrix is independent of the device project')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  for (const [width, height] of [[1920, 975], [1701, 863], [1440, 900], [1280, 800], [768, 1024], [390, 844], [360, 800]]) {
    await page.setViewportSize({ width: width!, height: height! })
    await page.goto('/settings/general')
    await expect(page.getByRole('combobox', { name: 'Sprache', exact: true })).toBeInViewport()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth && scrollY === 0)).toBe(true)
    if (width === 1701) {
      expect((await page.locator('.chat-rail').boundingBox())!.width).toBeCloseTo(60.25, 0)
      expect((await page.locator('.settings-sidebar').boundingBox())!.width).toBeCloseTo(333.1, 0)
      expect((await page.locator('.settings-content').boundingBox())!.width).toBeCloseTo(839.9, 0)
    }
    await navigation(page)
    await page.getByRole('textbox', { name: 'Einstellungen durchsuchen' }).fill('Sprache')
    await page.getByRole('textbox', { name: 'Einstellungen durchsuchen' }).press('Enter')
    await expect(page.getByRole('combobox', { name: 'Sprache', exact: true })).toBeFocused()
  }
  await page.setViewportSize({ width: 360, height: 420 })
  await navigation(page)
  await page.getByRole('textbox', { name: 'Einstellungen durchsuchen' }).fill('Dark Mode')
  await page.getByRole('textbox', { name: 'Einstellungen durchsuchen' }).press('Enter')
  await expect(page.getByRole('combobox', { name: 'Darstellung Einstellungen' })).toBeInViewport()
})
