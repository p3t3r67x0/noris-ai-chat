import { clearTestConversations } from './chat-fixtures'
import type { ApiSchemas } from '../../app/types/generated/api'
import { expect, test } from '@playwright/test'

test.setTimeout(60_000)

test.beforeEach(async ({ request }) => {
  await clearTestConversations(request)
  await request.put('/api/v1/chat/drafts/new', { data: { content: '' } })
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null, modelId: null } })
})

test('automatically completes Markdown on one node with a continuous streaming state', async ({ page, request }, info) => {
  const events: Array<{ type: string, messageId?: string, generationId?: string, seq?: number }> = []
  page.on('websocket', socket => socket.on('framereceived', frame => {
    const event = JSON.parse(String(frame.payload)) as typeof events[number]
    if (event.type.startsWith('chat.generation.')) events.push(event)
  }))
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const composer = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await composer.fill(`/long automatic ${info.project.name}`)
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
  await composer.press('Enter')
  const reply = page.locator('.message-assistant')
  await expect(reply).toHaveAttribute('data-status', 'streaming')
  const id = await reply.getAttribute('data-message-id')
  await expect(page.getByRole('button', { name: 'Antwort stoppen', exact: true })).toBeEnabled()
  await expect(reply.locator('.code-block')).toHaveCount(1)
  const scroller = page.locator('.chat-scroll')
  await scroller.evaluate(element => {
    element.dispatchEvent(new WheelEvent('wheel', { deltaY: -100 }))
    element.scrollTop = 0
    element.dispatchEvent(new Event('scroll'))
  })
  await expect(reply).toHaveAttribute('data-status', 'completed')
  expect(await scroller.evaluate(element => element.scrollTop)).toBeLessThanOrEqual(1)
  await expect(reply).toHaveAttribute('data-message-id', id!)
  await expect(reply.locator('.code-block')).toHaveCount(1)
  await expect(reply.locator('code')).toContainText("print('neu')")
  await expect(reply.locator('td')).toHaveCount(2)
  await expect(reply.locator('blockquote')).toHaveText('Zitat')
  await expect(reply).not.toContainText('Ausgabelimit erreicht')
  await expect(page.getByRole('button', { name: 'Weiterschreiben', exact: true })).toHaveCount(0)
  expect(events.filter(event => event.type === 'chat.generation.started')).toHaveLength(1)
  expect(events.filter(event => event.type === 'chat.generation.completed')).toHaveLength(1)
  expect(events.filter(event => event.type === 'chat.generation.incomplete')).toHaveLength(0)
  expect(new Set(events.map(event => event.messageId)).size).toBe(1)
  expect(new Set(events.map(event => event.generationId)).size).toBe(1)
  expect(events.map(event => event.seq)).toEqual(events.map((_, index) => index + 1))
  const conversation = (await (await request.get('/api/v1/conversations')).json()).conversations[0]
  const rows: ApiSchemas['MessageListResponse'] = await (await request.get(`/api/v1/conversations/${conversation.id}/messages`)).json()
  expect(rows.messages).toHaveLength(2)
  const stored = rows.messages.at(-1)!
  expect(stored).toMatchObject({ id, status: 'completed', continuationCount: 1, errorCode: null })
  expect(stored.content.match(/print\('alt'\)/g)).toHaveLength(3000)
  expect(stored.content.match(/print\('neu'\)/g)).toHaveLength(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
  await page.reload()
  await expect(reply).toHaveAttribute('data-message-id', id!)
  await expect(reply).toHaveAttribute('data-status', 'completed')
})

test('reload and WebSocket reconnect during an automatic continuation preserve the same answer', async ({ page, request }, info) => {
  // Hydration can finish while the authoritative bootstrap is still pending.
  // Keep that window open to exercise the send-button readiness guard reliably.
  let releaseBootstrap!: () => void
  const bootstrap = new Promise<void>(resolve => { releaseBootstrap = resolve })
  await page.route('**/api/v1/chat/drafts?**', async route => {
    await bootstrap
    await route.continue()
  })
  await page.addInitScript(() => {
    const Original = window.WebSocket
    const sockets: WebSocket[] = []
    Object.defineProperty(window, 'fixtureSockets', { value: sockets })
    window.WebSocket = class extends Original {
      constructor(url: string | URL, protocols?: string | string[]) { super(url, protocols); sockets.push(this) }
    }
  })
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const composer = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await composer.fill(`/long-stop reload ${info.project.name}`)
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeDisabled()
  releaseBootstrap()
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
  await composer.press('Enter')
  const reply = page.locator('.message-assistant')
  await expect(reply).toContainText("print('neu')", { timeout: 15_000 })
  await expect(reply).toHaveAttribute('data-status', 'streaming')
  const id = await reply.getAttribute('data-message-id')
  await page.reload()
  await expect(reply).toHaveAttribute('data-message-id', id!)
  await expect(reply).toHaveAttribute('data-status', 'streaming')
  await expect(reply).toContainText("print('neu')", { timeout: 15_000 })
  await page.evaluate(() => {
    const sockets = (window as typeof window & { fixtureSockets: WebSocket[] }).fixtureSockets
    sockets.at(-1)!.close()
  })
  await expect(reply).toHaveAttribute('data-status', 'completed', { timeout: 20_000 })
  const conversation = (await (await request.get('/api/v1/conversations')).json()).conversations[0]
  const rows: ApiSchemas['MessageListResponse'] = await (await request.get(`/api/v1/conversations/${conversation.id}/messages`)).json()
  expect(rows.messages).toHaveLength(2)
  const stored = rows.messages.at(-1)!
  expect(stored).toMatchObject({ id, status: 'completed', continuationCount: 1 })
  expect(stored.content.match(/print\('alt'\)/g)).toHaveLength(3000)
  expect(stored.content.match(/print\('neu'\)/g)).toHaveLength(1)
  expect(stored.content.match(/ weiterer Text/g)).toHaveLength(100)
  await expect(reply.locator('code')).toHaveCount(1)
})

test('Stop during automatic continuation keeps all persisted text after reload', async ({ page, request }, info) => {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const composer = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await composer.fill(`/long-stop stop ${info.project.name}`)
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
  await composer.press('Enter')
  const reply = page.locator('.message-assistant')
  await expect(reply).toContainText("print('neu')", { timeout: 15_000 })
  const id = await reply.getAttribute('data-message-id')
  await page.getByRole('button', { name: 'Antwort stoppen', exact: true }).click()
  await expect(reply).toHaveAttribute('data-status', 'cancelled')
  const conversation = (await (await request.get('/api/v1/conversations')).json()).conversations[0]
  const rows: ApiSchemas['MessageListResponse'] = await (await request.get(`/api/v1/conversations/${conversation.id}/messages`)).json()
  expect(rows.messages).toHaveLength(2)
  expect(rows.messages.at(-1)).toMatchObject({ id, status: 'cancelled', continuationCount: 1 })
  expect(rows.messages.at(-1)!.content.match(/print\('alt'\)/g)).toHaveLength(3000)
  expect(rows.messages.at(-1)!.content.match(/print\('neu'\)/g)).toHaveLength(1)
  await page.reload()
  await expect(reply).toHaveAttribute('data-status', 'cancelled')
  await expect(reply).toHaveAttribute('data-message-id', id!)
  await expect(reply).toContainText("print('neu')", { timeout: 15_000 })
  await expect(page.getByRole('button', { name: 'Weiterschreiben', exact: true })).toBeVisible()
})
