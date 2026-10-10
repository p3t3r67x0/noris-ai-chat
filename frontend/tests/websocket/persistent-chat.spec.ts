import type { ApiSchemas } from '../../app/types/generated/api'
import { expect, test } from '@playwright/test'

test.beforeEach(async ({ request }) => {
  let cursor: string | null = null
  do {
    const response = await request.get('/api/v1/conversations', { params: { archived: true, limit: 100, ...(cursor ? { cursor } : {}) } })
    expect(response.ok()).toBe(true)
    const data: ApiSchemas['ConversationListResponse'] = await response.json()
    for (const c of data.conversations) await request.delete(`/api/v1/conversations/${c.id}`)
    cursor = data.nextCursor ?? null
  } while (cursor)
  await request.put('/api/v1/chat/drafts/new', { data: { content: '' } })
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null, modelId: null } })
})

test('persists incremental streaming, drafts and generated title through reload', async ({ page, request }) => {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const composer = page.getByRole('textbox', { name: 'Nachricht' })
  await expect(composer).toBeEnabled()
  await composer.fill('Persistenz prüfen')
  await composer.press('Enter')
  await expect(page.locator('[data-generation-status="streaming"]')).toBeAttached()
  await expect(page.locator('.chat-timeline')).toContainText('Echte')
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  const list = await request.get('/api/v1/conversations')
  const conversation = (await list.json()).conversations[0]
  const rows = await request.get(`/api/v1/conversations/${conversation.id}/messages`)
  expect((await rows.json()).messages.at(-1).content).toBe('Echte HTTP-Antwort mit Grüße 🌍.')
  await expect.poll(async () => (await (await request.get(`/api/v1/conversations/${conversation.id}`)).json()).titleSource).toBe('generated')
  await composer.fill('Nicht abgesendeter Entwurf')
  await expect.poll(async () => (await (await request.get('/api/v1/chat/drafts')).json()).drafts.find((d: { key: string }) => d.key === conversation.id)?.content).toBe('Nicht abgesendeter Entwurf')
  await page.reload()
  await expect(composer).toHaveValue('Nicht abgesendeter Entwurf')
  await expect(page.locator('.chat-timeline')).toContainText('Echte HTTP-Antwort mit Grüße 🌍.')
  expect(await page.evaluate(() => scrollX)).toBe(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('stop and reload retain partial answer; retry creates another immutable variant', async ({ page, request }, info) => {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const composer = page.getByRole('textbox', { name: 'Nachricht' })
  await composer.fill('/quiet')
  await composer.press('Enter')
  await expect(page.locator('[data-generation-status="streaming"]')).toBeAttached()
  await page.getByRole('button', { name: 'Antwort stoppen', exact: true }).click()
  await expect(page.locator('[data-generation-status="cancelled"]')).toBeAttached()
  await expect(composer).toBeFocused()
  await page.reload()
  await expect(page.locator('.chat-timeline')).toContainText('/quiet')
  const c = (await (await request.get('/api/v1/conversations')).json()).conversations[0]
  const rows = (await (await request.get(`/api/v1/conversations/${c.id}/messages`)).json()).messages
  expect(rows.at(-1).status).toBe('cancelled')
  await composer.fill(`/retry ws persistence ${info.project.name} ${globalThis.crypto.randomUUID()}`)
  await composer.press('Enter')
  await expect(page.locator('[data-generation-status="failed"]')).toBeAttached()
  await page.getByRole('button', { name: 'Erneut versuchen', exact: true }).click()
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  const nextRows = (await (await request.get(`/api/v1/conversations/${c.id}/messages`)).json()).messages
  expect(nextRows.filter((m: { role: string }) => m.role === 'assistant')).toHaveLength(3)
})

test('reload during generation resumes without duplicated text', async ({ page, request }) => {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const composer = page.getByRole('textbox', { name: 'Nachricht' })
  await composer.fill('Reload während Streaming')
  await composer.press('Enter')
  await expect(page.locator('[data-generation-status="streaming"]')).toBeAttached()
  await page.reload()
  await expect(page.locator('.chat-timeline')).toContainText('Echte HTTP-Antwort mit Grüße 🌍.')
  const c = (await (await request.get('/api/v1/conversations')).json()).conversations[0]
  const rows = (await (await request.get(`/api/v1/conversations/${c.id}/messages`)).json()).messages
  expect(rows).toHaveLength(2)
  expect(rows.at(-1).content).toBe('Echte HTTP-Antwort mit Grüße 🌍.')
})


test('continuation creates an immutable sibling and persists selected variants after reload', async ({ page, request }, info) => {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await page.getByRole('button', { name: 'Modell auswählen', exact: true }).click()
  await page.getByRole('option', { name: 'Fixture Long' }).click()
  const composer = page.getByRole('textbox', { name: 'Nachricht' })
  await composer.fill(`/length ws ${info.project.name}`)
  await composer.press('Enter')
  await expect(page.locator('.message-assistant')).toHaveAttribute('data-status', 'incomplete')
  const original = await page.locator('.message-assistant').getAttribute('data-message-id')
  await page.reload()
  await expect(page.locator('.message-assistant')).toHaveAttribute('data-status', 'incomplete')
  await expect(page.getByRole('button', { name: 'Modell auswählen', exact: true })).toContainText('Fixture Long')
  await page.getByRole('button', { name: 'Weiterschreiben', exact: true }).click()
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  const continued = await page.locator('.message-assistant').getAttribute('data-message-id')
  expect(continued).not.toBe(original)
  const c = (await (await request.get('/api/v1/conversations')).json()).conversations[0]
  const rows = (await (await request.get(`/api/v1/conversations/${c.id}/messages`)).json()).messages
  expect(rows.find((m: { id: string }) => m.id === original).content).toBe(' token'.repeat(9000))
  expect(rows.find((m: { id: string }) => m.id === continued).content.startsWith(' token'.repeat(9000))).toBe(true)
  await page.getByRole('button', { name: 'Vorherige Antwortvariante' }).click()
  await expect.poll(async () => (await (await request.get(`/api/v1/conversations/${c.id}`)).json()).activeLeafMessageId).toBe(original)
  await page.reload()
  await expect(page.locator('.message-assistant')).toHaveAttribute('data-message-id', original!)
  await page.getByRole('button', { name: 'Nächste Antwortvariante' }).click()
  await expect(page.locator('.message-assistant')).toHaveAttribute('data-message-id', continued!)
})


test('manual title, archive, restore and deletion are persisted from the existing sidebar', async ({ page, request }) => {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const composer = page.getByRole('textbox', { name: 'Nachricht' })
  await composer.fill('Chatverwaltung prüfen')
  await composer.press('Enter')
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  const c = (await (await request.get('/api/v1/conversations')).json()).conversations[0]
  const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
  const sidebar = async () => { if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click() }
  await sidebar()
  const row = page.locator(`[data-conversation-id="${c.id}"]`)
  await row.getByRole('button', { name: /^Aktionen für/ }).click()
  await page.getByRole('menuitem', { name: 'Umbenennen', exact: true }).click()
  await page.getByRole('textbox', { name: 'Chat-Titel' }).fill('Mein manueller Titel')
  await page.getByRole('button', { name: 'Speichern', exact: true }).click()
  await expect.poll(async () => (await (await request.get(`/api/v1/conversations/${c.id}`)).json()).titleSource).toBe('manual')
  await page.reload()
  await sidebar()
  await expect(row.locator('button').first()).toHaveAttribute('title', 'Mein manueller Titel')
  await row.getByRole('button', { name: /^Aktionen für/ }).click()
  await page.getByRole('menuitem', { name: 'Archivieren', exact: true }).click()
  await expect.poll(async () => (await (await request.get('/api/v1/conversations')).json()).conversations.length).toBe(0)
  await page.getByRole('button', { name: 'Archivierte Chats', exact: true }).first().click()
  await page.getByRole('button', { name: 'Mein manueller Titel wiederherstellen' }).click()
  await expect.poll(async () => (await (await request.get('/api/v1/conversations')).json()).conversations.length).toBe(1)
  await sidebar()
  await row.getByRole('button', { name: /^Aktionen für/ }).click()
  await page.getByRole('menuitem', { name: 'Löschen', exact: true }).click()
  await page.getByRole('dialog', { name: 'Chat löschen?' }).getByRole('button', { name: 'Chat löschen', exact: true }).click()
  await expect.poll(async () => (await request.get(`/api/v1/conversations/${c.id}`)).status()).toBe(404)
})

test('manual rename survives a version conflict after automatic title generation', async ({ page, request }) => {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const composer = page.getByRole('textbox', { name: 'Nachricht' })
  await composer.fill('Titelkonflikt prüfen')
  await composer.press('Enter')
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  const c = (await (await request.get('/api/v1/conversations')).json()).conversations[0]
  const path = `/api/v1/conversations/${c.id}`
  await expect.poll(async () => (await (await request.get(path)).json()).titleSource).toBe('generated')
  let injected = false
  await page.route(`**${path}`, async (route) => {
    const body = route.request().postDataJSON()
    if (!injected && route.request().method() === 'PATCH' && body?.title === 'Mein manueller Titel') {
      // Commit concurrent metadata after the client's PATCH captured its revision.
      injected = true
      const current = await (await request.get(path)).json()
      const update = await request.patch(path, { data: { archived: false, version: current.version } })
      expect(update.ok()).toBe(true)
      await route.continue()
    }
    else await route.continue()
  })
  const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  const row = page.locator(`[data-conversation-id="${c.id}"]`)
  await row.getByRole('button', { name: /^Aktionen für/ }).click()
  await page.getByRole('menuitem', { name: 'Umbenennen', exact: true }).click()
  await page.getByRole('textbox', { name: 'Chat-Titel' }).fill('Mein manueller Titel')
  const conflict = page.waitForResponse(response => response.url().endsWith(path) && response.request().method() === 'PATCH' && response.status() === 409)
  await page.getByRole('button', { name: 'Speichern', exact: true }).click()
  await conflict
  await expect.poll(async () => {
    const saved = await (await request.get(path)).json()
    return { title: saved.title, titleSource: saved.titleSource }
  }).toEqual({ title: 'Mein manueller Titel', titleSource: 'manual' })
  await page.reload()
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  await expect(row.locator('button').first()).toHaveAttribute('title', 'Mein manueller Titel')
})
