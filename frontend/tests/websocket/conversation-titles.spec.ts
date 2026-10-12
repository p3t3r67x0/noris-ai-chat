import { expect, test } from '@playwright/test'
import type { ApiSchemas } from '../../app/types/generated/api'

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

for (const [index, name] of ['DeepSeek V4.1 Flash', 'GPT-OSS 120B'].entries()) {
  test(`${name}: sidebar titles stay consistent across tabs, reconnect, reload and regeneration`, async ({ page, context, request }) => {
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
