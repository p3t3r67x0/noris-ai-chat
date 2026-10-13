import { clearTestConversations } from './chat-fixtures'
import { expect, test } from '@playwright/test'
import type { Locator, Page } from '@playwright/test'
import { openDataControls, returnToChat } from '../e2e/settings-helpers'

test.beforeEach(async ({ request }) => {
  await clearTestConversations(request)
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null } })
})

function localSnapshot() {
  const id = crypto.randomUUID(), user = crypto.randomUUID(), reply = crypto.randomUUID(), variant = crypto.randomUUID()
  const time = new Date().toISOString()
  const snapshot = { version: 1, conversations: { version: 1, activeConversationId: id, conversations: { [id]: { id, title: 'Synthetischer lokaler Import', titleSource: 'manual', titleGenerationAttempted: true, createdAt: time, updatedAt: time, archivedAt: null, activeLeafMessageId: reply } } }, messages: {
    [user]: { id: user, conversationId: id, parentMessageId: null, role: 'user', content: 'Synthetische lokale Frage', status: 'completed', createdAt: time },
    [reply]: { id: reply, conversationId: id, parentMessageId: user, role: 'assistant', content: 'Synthetische lokale Antwort', status: 'completed', createdAt: time },
    [variant]: { id: variant, conversationId: id, parentMessageId: user, role: 'assistant', content: 'Synthetische Variante', status: 'completed', createdAt: time },
  }, drafts: { [id]: 'Synthetischer lokaler Entwurf' }, preferredLeaves: { [user]: reply } }
  return { id, user, reply, variant, snapshot }
}

async function seedLocal(page: Page, raw: string, theme: string) {
  await page.addInitScript(({ raw, theme }) => {
    localStorage.setItem('noris-ai:chat:v1', raw)
    localStorage.setItem('noris-ai-theme', theme)
  }, { raw, theme })
  await page.goto('/')
  await expect(page.locator('.chat-main').getByText('Lokale Chats importieren', { exact: true })).toHaveCount(0)
}

async function importResult(settings: Locator, content: string): Promise<void> {
  const result = settings.locator('details').filter({ hasText: 'Letztes Importergebnis' })
  await expect(result.locator('summary')).toBeVisible()
  if (await result.getAttribute('open') === null) await result.locator('summary').click()
  await expect(result.locator('p')).toContainText(content)
}

for (const theme of ['light', 'dark']) {
  test(`imports from data controls only after confirmation and skips duplicates in ${theme}`, async ({ page, request }, testInfo) => {
    const { id, user, reply, variant, snapshot } = localSnapshot()
    const raw = JSON.stringify(snapshot)
    await seedLocal(page, raw, theme)
    const settings = await openDataControls(page)
    await expect(settings).toContainText('Übertrage bisher lokal gespeicherte Unterhaltungen in die PostgreSQL-Datenbank.')
    await expect(settings.getByRole('button', { name: 'Importieren', exact: true })).toBeEnabled()
    await page.screenshot({ path: testInfo.outputPath(`settings-data-controls-${theme}.png`), animations: 'disabled' })
    expect((await request.get(`/api/v1/conversations/${id}`)).status()).toBe(404)
    await settings.getByRole('button', { name: 'Importieren', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Lokale Chats importieren', exact: true })
    await expect(dialog).toContainText('Die lokale Sicherung bleibt erhalten')
    expect((await request.get(`/api/v1/conversations/${id}`)).status()).toBe(404)
    await dialog.getByRole('button', { name: 'Import ausdrücklich starten' }).click()
    await importResult(settings, '1 Chats importiert')
    await expect(dialog).not.toBeVisible()
    const result = (await (await request.get(`/api/v1/conversations/${id}/messages`)).json()).messages
    expect(result.map((m: { id: string }) => m.id).sort()).toEqual([user, reply, variant].sort())
    expect(result.find((m: { id: string }) => m.id === reply).content).toBe(snapshot.messages[reply]!.content)
    expect(await page.evaluate(() => localStorage.getItem('noris-ai:chat:v1'))).toBe(raw)
    await settings.getByRole('button', { name: 'Importieren', exact: true }).click()
    await dialog.getByRole('button', { name: 'Import ausdrücklich starten' }).click()
    await importResult(settings, '0 Chats importiert, 1 bereits vorhanden')
    await expect(dialog).not.toBeVisible()
    const again = (await (await request.get(`/api/v1/conversations/${id}/messages`)).json()).messages
    expect(again).toEqual(result)
    await returnToChat(page)
    await expect(settings).not.toBeVisible()
    await expect(page.getByRole('textbox', { name: 'Nachricht', exact: true })).toHaveValue('Synthetischer lokaler Entwurf')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.reload()
    await expect(page.getByRole('textbox', { name: 'Nachricht', exact: true })).toHaveValue('Synthetischer lokaler Entwurf')
    expect(await page.evaluate(() => localStorage.getItem('noris-ai:chat:v1'))).toBe(raw)
  })

  test(`cancel and Escape retain local data without importing in ${theme}`, async ({ page, request }) => {
    const { id, snapshot } = localSnapshot()
    const raw = JSON.stringify(snapshot)
    let imports = 0
    page.on('request', req => { if (req.url().endsWith('/conversations/import') && req.method() === 'POST') imports++ })
    await seedLocal(page, raw, theme)
    const settings = await openDataControls(page)
    for (const cancel of ['button', 'escape']) {
      await settings.getByRole('button', { name: 'Importieren', exact: true }).click()
      const dialog = page.getByRole('dialog', { name: 'Lokale Chats importieren', exact: true })
      if (cancel === 'button') await dialog.getByRole('button', { name: 'Abbrechen', exact: true }).click()
      else await page.keyboard.press('Escape')
      await expect(dialog).not.toBeVisible()
      await expect(settings).toBeVisible()
      await expect(settings.getByRole('button', { name: 'Importieren', exact: true })).toBeFocused()
    }
    expect(imports).toBe(0)
    expect((await request.get(`/api/v1/conversations/${id}`)).status()).toBe(404)
    expect(await page.evaluate(() => localStorage.getItem('noris-ai:chat:v1'))).toBe(raw)
  })

  test(`import failure is reported and permits retry without losing the backup in ${theme}`, async ({ page, request }) => {
    const { id, snapshot } = localSnapshot()
    const raw = JSON.stringify(snapshot)
    await page.route('**/api/v1/conversations/import', route => route.fulfill({ status: 503, json: { error: { code: 'CHAT_UNAVAILABLE', message: 'Synthetischer Importfehler. Bitte erneut versuchen.' } } }))
    await seedLocal(page, raw, theme)
    const settings = await openDataControls(page)
    await settings.getByRole('button', { name: 'Importieren', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Lokale Chats importieren', exact: true })
    await dialog.getByRole('button', { name: 'Import ausdrücklich starten' }).click()
    await importResult(settings, 'Die Aktion konnte gerade nicht ausgeführt werden.')
    await expect(page.locator('.app-notification')).toContainText('Chats konnten nicht importiert werden.')
    await expect(dialog).not.toBeVisible()
    expect((await request.get(`/api/v1/conversations/${id}`)).status()).toBe(404)
    expect(await page.evaluate(() => localStorage.getItem('noris-ai:chat:v1'))).toBe(raw)
    await page.unroute('**/api/v1/conversations/import')
    await settings.getByRole('button', { name: 'Importieren', exact: true }).click()
    await dialog.getByRole('button', { name: 'Import ausdrücklich starten' }).click()
    await importResult(settings, '1 Chats importiert')
  })

  test(`a conflicting chat prevents partial imports and preserves database data in ${theme}`, async ({ page, request }) => {
    const { id, snapshot } = localSnapshot()
    const created = await request.post('/api/v1/conversations', { data: { id, title: 'Bereits vorhandener synthetischer Chat' } })
    expect(created.ok()).toBe(true)
    const before = await created.json()
    const other = localSnapshot()
    Object.assign(snapshot.conversations.conversations, other.snapshot.conversations.conversations)
    Object.assign(snapshot.messages, other.snapshot.messages)
    Object.assign(snapshot.drafts, other.snapshot.drafts)
    const raw = JSON.stringify(snapshot)
    await seedLocal(page, raw, theme)
    const settings = await openDataControls(page)
    await settings.getByRole('button', { name: 'Importieren', exact: true }).click()
    await page.getByRole('dialog', { name: 'Lokale Chats importieren', exact: true }).getByRole('button', { name: 'Import ausdrücklich starten' }).click()
    await importResult(settings, 'Der Import enthält Konflikte')
    expect(await (await request.get(`/api/v1/conversations/${id}`)).json()).toEqual(before)
    expect((await request.get(`/api/v1/conversations/${other.id}`)).status()).toBe(404)
    expect(await page.evaluate(() => localStorage.getItem('noris-ai:chat:v1'))).toBe(raw)
  })

  test(`an invalid snapshot never reaches PostgreSQL in ${theme}`, async ({ page }) => {
    let imports = 0
    page.on('request', req => { if (req.url().endsWith('/conversations/import') && req.method() === 'POST') imports++ })
    await seedLocal(page, '{synthetic-invalid-snapshot', theme)
    const settings = await openDataControls(page)
    await settings.getByRole('button', { name: 'Importieren', exact: true }).click()
    await page.getByRole('dialog', { name: 'Lokale Chats importieren', exact: true }).getByRole('button', { name: 'Import ausdrücklich starten' }).click()
    await importResult(settings, 'Die lokale Chatsicherung konnte nicht gelesen werden. Sie bleibt erhalten.')
    expect(imports).toBe(0)
    expect(await page.evaluate(() => localStorage.getItem('noris-ai:chat:v1'))).toBe('{synthetic-invalid-snapshot')
  })
}
