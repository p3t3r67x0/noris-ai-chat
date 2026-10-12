import { expect, test } from '@playwright/test'
import type { Page, WebSocketRoute } from '@playwright/test'
import type { ApiSchemas } from '../../app/types/generated/api'
import type { ChatWsEvent } from '../../app/types/generated/chat-ws'

const providerURL = `http://127.0.0.1:${process.env.NORIS_E2E_PROVIDER_PORT ?? 8591}`
const nativeModels = ['vllm/qsu/deepseek-v41-flash', 'vllm/release/gpt-oss-120b']

test.setTimeout(60_000)

test.beforeEach(async ({ request }) => {
  const result: ApiSchemas['ConversationListResponse'] = await (await request.get('/api/v1/conversations', { params: { archived: true, limit: 100 } })).json()
  for (const value of result.conversations) await request.delete(`/api/v1/conversations/${value.id}`)
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null, modelId: null } })
  await request.put('/api/v1/chat/drafts/new', { data: { content: '' } })
  await request.post(`${providerURL}/fixture/catalog`, { data: { ids: ['fixture-alpha', 'fixture-beta', 'fixture-long', ...nativeModels] } })
  await expect.poll(async () => {
    const catalog = await (await request.get('/api/v1/llm/models')).json()
    return catalog.models.map((model: { id: string }) => model.id)
  }).toEqual(expect.arrayContaining(nativeModels))
})
test.afterEach(async ({ request }) => {
  await request.post(`${providerURL}/fixture/catalog`, { data: { ids: ['fixture-alpha', 'fixture-beta', 'fixture-long'] } })
})

async function openSidebar(page: Page): Promise<void> {
  const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  await expect(page.getByRole('navigation', { name: 'Gespräche', exact: true })).toBeVisible()
}

const sidebarRow = (page: Page, id: string) => page.locator(`.conversation-row[data-conversation-id="${id}"]`).filter({ visible: true })

for (const eventType of ['chat.title.updated', 'chat.conversation.updated'] as const) {
  test(`${eventType}: a wide authoritative title updates both sidebars after switching chats and survives stale events and reload`, async ({ page, context, request }) => {
    const queued: Array<{ client: WebSocketRoute, event: ChatWsEvent, message: string | Buffer }> = []
    const clients: WebSocketRoute[] = []
    let holding = true
    await context.routeWebSocket('**/api/v1/chat/ws', client => {
      clients.push(client)
      const server = client.connectToServer()
      server.onMessage(message => {
        const event = JSON.parse(String(message)) as ChatWsEvent
        if (holding && (event.type === 'chat.title.updated' || (event.type === 'chat.conversation.updated' && event.conversation.titleSource === 'generated'))) {
          queued.push({ client, event, message })
          return
        }
        client.send(message)
      })
    })
    const other = await context.newPage()
    await Promise.all([page.goto('/'), other.goto('/')])
    for (const tab of [page, other]) await expect(tab.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    const before = (await (await request.get(`${providerURL}/fixture/state`)).json()).title_calls.length
    const composer = page.getByRole('textbox', { name: 'Nachricht', exact: true })
    await expect(composer).toBeEnabled()
    await composer.fill('/title-summary-switch')
    await composer.press('Enter')
    await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
    const conversation = (await (await request.get('/api/v1/conversations')).json()).conversations[0] as ApiSchemas['ConversationResponse']
    const path = `/api/v1/conversations/${conversation.id}`
    // Navigate while the separate title provider call is still pending.
    await openSidebar(page)
    await page.locator('.sidebar-primary-actions').getByRole('button', { name: 'Neuer Chat', exact: true }).click()
    await expect(page.locator('.message-assistant')).toHaveCount(0)
    await expect.poll(async () => (await (await request.get(path)).json()).titleSource).toBe('generated')
    const saved = await (await request.get(path)).json() as ApiSchemas['ConversationResponse']
    expect(saved.title).toBe('Automatische Chat-Zusammenfassungen')
    expect(saved.version).toBeGreaterThan(conversation.version)
    await expect.poll(() => queued.filter(item => item.event.type === eventType).length).toBe(2)
    // Deliver only one metadata event type. The other remains withheld, so each
    // transport handler must independently synchronize the rendered records.
    for (const item of queued.filter(item => item.event.type === eventType)) item.client.send(item.message)
    holding = false
    for (const tab of [page, other]) {
      await openSidebar(tab)
      const row = sidebarRow(tab, conversation.id)
      await expect(row.locator('button').first()).toHaveAttribute('title', saved.title)
      await expect(row.locator('[data-title-source]')).toHaveAttribute('data-title-source', 'generated')
      await expect(row.locator('[data-title-source]')).toHaveText(saved.title)
    }
    clients.length = 0
    for (const tab of [page, other]) {
      await tab.reload()
      await expect(tab.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      await openSidebar(tab)
      const row = sidebarRow(tab, conversation.id)
      await expect(row.locator('button').first()).toHaveAttribute('title', saved.title)
      await expect(row.locator('[data-title-source]')).toHaveAttribute('data-title-source', 'generated')
      await expect(row.locator('[data-title-source]')).toHaveText(saved.title)
    }
    await expect.poll(() => clients.length).toBe(2)
    const renamed = await request.patch(path, { data: { title: 'Meine manuellen Zusammenfassungen', version: saved.version } })
    expect(renamed.ok()).toBe(true)
    for (const tab of [page, other]) await expect(sidebarRow(tab, conversation.id).locator('button').first()).toHaveAttribute('title', 'Meine manuellen Zusammenfassungen')
    const conflict = await request.patch(path, { data: { title: 'Titel aus einem veralteten Tab', version: saved.version } })
    expect(conflict.status()).toBe(409)
    expect(await conflict.json()).toMatchObject({ error: { code: 'VERSION_CONFLICT' } })
    for (const client of clients) {
      client.send(JSON.stringify({ version: 1, type: 'chat.conversation.updated', conversation: saved }))
      client.send(JSON.stringify({ version: 1, type: 'chat.title.updated', conversationId: conversation.id, title: saved.title, titleSource: 'generated' }))
    }
    for (const tab of [page, other]) {
      const row = sidebarRow(tab, conversation.id)
      await expect(row.locator('[data-title-source]')).toHaveAttribute('data-title-source', 'manual')
      await expect(row.locator('button').first()).toHaveAttribute('title', 'Meine manuellen Zusammenfassungen')
      await tab.reload()
      await expect(tab.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      await openSidebar(tab)
      await expect(row.locator('button').first()).toHaveAttribute('title', 'Meine manuellen Zusammenfassungen')
      await expect(row.locator('[data-title-source]')).toHaveAttribute('data-title-source', 'manual')
    }
    expect((await (await request.get(`${providerURL}/fixture/state`)).json()).title_calls.length - before).toBe(1)
    await other.close()
  })
}

test('a manual title committed during title generation wins immediately in every tab', async ({ page, context, request }) => {
  const titleEvents: ChatWsEvent[] = []
  page.on('websocket', socket => socket.on('framereceived', ({ payload }) => {
    const event = JSON.parse(String(payload)) as ChatWsEvent
    if (event.type === 'chat.title.updated') titleEvents.push(event)
  }))
  const other = await context.newPage()
  await Promise.all([page.goto('/'), other.goto('/')])
  for (const tab of [page, other]) await expect(tab.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const before = (await (await request.get(`${providerURL}/fixture/state`)).json()).title_calls.length
  const composer = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await expect(composer).toBeEnabled()
  await composer.fill('/title-summary-switch')
  await composer.press('Enter')
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  await expect.poll(async () => (await (await request.get(`${providerURL}/fixture/state`)).json()).title_calls.length).toBe(before + 1)
  const conversation = (await (await request.get('/api/v1/conversations')).json()).conversations[0] as ApiSchemas['ConversationResponse']
  expect(conversation.titleSource).toBe('fallback')
  const path = `/api/v1/conversations/${conversation.id}`
  expect((await request.patch(path, { data: { title: 'Meine eigenen Notizen', version: conversation.version } })).ok()).toBe(true)
  for (const tab of [page, other]) {
    await openSidebar(tab)
    await expect(sidebarRow(tab, conversation.id).locator('button').first()).toHaveAttribute('title', 'Meine eigenen Notizen')
  }
  await expect.poll(() => titleEvents.some(event => event.type === 'chat.title.updated' && event.conversationId === conversation.id && event.titleSource === 'manual')).toBe(true)
  expect((await (await request.get(path)).json()).titleSource).toBe('manual')
  expect((await (await request.get(`${providerURL}/fixture/state`)).json()).title_calls.length - before).toBe(1)
  await other.close()
})

for (const [index, name] of ['DeepSeek V4.1 Flash', 'GPT-OSS 120B'].entries()) {
  test(`${name}: sidebar titles stay consistent across tabs, reconnect, reload and regeneration`, async ({ page, context, request }) => {
    // Keep the verified catalog stable while exercising the title lifecycle.
    // One-second catalog expiry and model refresh have separate coverage.
    await context.route('**/api/v1/llm/models', async route => {
      const response = await route.fetch()
      const catalog = await response.json()
      await route.fulfill({ response, json: { ...catalog, expires_in_seconds: 60 } })
    })
    await context.addInitScript(() => {
      const sockets: WebSocket[] = []
      const NativeSocket = window.WebSocket
      window.WebSocket = class extends NativeSocket {
        constructor(url: string | URL, protocols?: string | string[]) { super(url, protocols); sockets.push(this) }
      }
      Object.defineProperty(window, 'dropChatSockets', { value: () => sockets.forEach(socket => socket.close()) })
    })
    const other = await context.newPage()
    await Promise.all([page.goto('/'), other.goto('/')])
    for (const tab of [page, other]) await expect(tab.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    await page.getByRole('button', { name: 'Modell auswählen', exact: true }).click()
    await page.getByRole('option', { name: new RegExp(`^${name}`) }).click()
    const before = (await (await request.get(`${providerURL}/fixture/state`)).json()).title_calls.length
    const composer = page.getByRole('textbox', { name: 'Nachricht', exact: true })
    await expect(composer).toBeEnabled()
    await composer.fill('/title-reasoning Docker DNS')
    await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
    await composer.press('Enter')
    await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
    const conversation = (await (await request.get('/api/v1/conversations')).json()).conversations[0]
    const path = `/api/v1/conversations/${conversation.id}`
    await expect.poll(async () => (await (await request.get(path)).json()).titleSource).toBe('generated')
    const saved = await (await request.get(path)).json()
    for (const tab of [page, other]) {
      const toggle = tab.locator('.chat-header button[aria-controls="chat-sidebar"]')
      if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
      await expect(tab.locator(`[data-conversation-id="${conversation.id}"] button`).first()).toHaveAttribute('title', saved.title)
    }
    // Drop the idle tab's connection while a manual update commits; its fresh
    // connection must reconcile metadata without another chat/provider call.
    await context.setOffline(true)
    for (const tab of [page, other]) await tab.evaluate(() => (window as unknown as { dropChatSockets: () => void }).dropChatSockets())
    const renamed = await request.patch(path, { data: { title: 'Mein manueller Titel', version: saved.version } })
    expect(renamed.ok()).toBe(true)
    await context.setOffline(false)
    for (const tab of [page, other]) {
      await expect(tab.locator(`[data-conversation-id="${conversation.id}"] button`).first()).toHaveAttribute('title', 'Mein manueller Titel')
      await tab.reload()
      await expect(tab.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      const toggle = tab.locator('.chat-header button[aria-controls="chat-sidebar"]')
      if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
      await expect(tab.locator(`[data-conversation-id="${conversation.id}"] button`).first()).toHaveAttribute('title', 'Mein manueller Titel')
    }
    const current = await (await request.get(path)).json()
    expect((await request.patch(path, { data: { title: 'Titel aus zweitem Tab', version: current.version } })).ok()).toBe(true)
    for (const tab of [page, other]) await expect(tab.locator(`[data-conversation-id="${conversation.id}"] button`).first()).toHaveAttribute('title', 'Titel aus zweitem Tab')
    const closeSidebar = page.getByRole('button', { name: 'Gesprächsliste schließen', exact: true })
    if (await closeSidebar.isVisible()) await closeSidebar.click()
    await page.locator('.message-assistant').last().getByRole('button', { name: 'Antwort erneut generieren', exact: true }).click()
    await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
    const state = await (await request.get(`${providerURL}/fixture/state`)).json()
    expect(state.title_calls.length - before).toBe(1)
    expect(state.title_calls.at(-1).model).toBe(nativeModels[index])
    expect(state.title_calls.at(-1).max_tokens).toBe(1024)
    expect((await (await request.get(path)).json()).titleSource).toBe('manual')
    await other.close()
  })
}
