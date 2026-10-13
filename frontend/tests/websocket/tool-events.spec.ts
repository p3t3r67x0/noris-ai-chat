import { expect, test } from '@playwright/test'
import { clearTestConversations } from './chat-fixtures'
import { validateToolEvent } from '../../app/lib/chat/toolEvents'
import type { ToolWsEvent } from '../../app/lib/chat/toolEvents'

test.skip(Boolean(process.env.NORIS_E2E_COMPOSE_URL), 'Local deterministic tool fixture is selected by the WebSocket test server')

test.beforeEach(async ({ request }) => {
  await clearTestConversations(request)
  await request.put('/api/v1/chat/drafts/new', { data: { content: '' } })
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null, modelId: null } })
})

for (const theme of ['light', 'dark'] as const) {
  test(`parallel tool states, persistent terminal replay and reload (${theme})`, async ({ page, request }) => {
    const events: ToolWsEvent[] = []
    page.on('websocket', socket => socket.on('framereceived', frame => {
      const value: unknown = JSON.parse(String(frame.payload))
      if (validateToolEvent(value)) events.push(value)
    }))
    await page.addInitScript((preference) => { localStorage.setItem('noris-ai-theme', preference) }, theme)
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    const composer = page.getByRole('textbox', { name: 'Nachricht', exact: true })
    await composer.fill('/p2-parallel')
    await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
    await composer.press('Enter')
    await expect.poll(() => events.filter(event => event.type === 'tool.started').length).toBe(2)
    await expect(page.locator('[data-generation-status="streaming"]')).toBeAttached()
    await expect(page.locator('.message-assistant').last()).toHaveAttribute('data-status', 'completed')
    const completed = events.filter(event => event.type === 'tool.completed')
    expect(completed).toHaveLength(2)
    for (const event of completed) {
      if (event.type === 'tool.snapshot') throw new Error('Expected lifecycle event')
      expect(event.payload.result?.sourceCount).toBe(5)
      const response = await request.get(`/api/v1/chat/tool-runs/${event.runId}`)
      expect(response.ok()).toBe(true)
      expect((await response.json()).run.state).toBe('succeeded')
    }
    events.length = 0
    await page.reload()
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    await expect.poll(() => events.flatMap(event => event.type === 'tool.snapshot' ? event.runs : []).filter(run => run.state === 'succeeded').length).toBe(2)
    await expect(page.locator('.message-assistant').last()).toHaveAttribute('data-status', 'completed')
    expect(JSON.stringify(events)).not.toContain('Deterministic local fixture')
    expect(JSON.stringify(events)).not.toContain('policy_snapshot')
  })

  test(`disconnect, replay, stop and safe failure (${theme})`, async ({ page }) => {
    const events: ToolWsEvent[] = []
    page.on('websocket', socket => socket.on('framereceived', frame => {
      const value: unknown = JSON.parse(String(frame.payload))
      if (validateToolEvent(value)) events.push(value)
    }))
    await page.addInitScript((preference) => {
      localStorage.setItem('noris-ai-theme', preference)
      const sockets: WebSocket[] = []
      const Original = window.WebSocket
      window.WebSocket = class extends Original {
        constructor(url: string | URL, protocols?: string | string[]) { super(url, protocols); sockets.push(this) }
      }
      Object.defineProperty(window, 'p2Disconnect', { value: () => sockets.forEach(socket => socket.close()) })
    }, theme)
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    const composer = page.getByRole('textbox', { name: 'Nachricht', exact: true })
    await composer.fill('/p2-slow')
    await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
    await composer.press('Enter')
    await expect.poll(() => events.some(event => event.type === 'tool.started')).toBe(true)
    await page.evaluate(() => (window as unknown as { p2Disconnect: () => void }).p2Disconnect())
    await expect.poll(() => events.some(event => event.type === 'tool.snapshot' && event.runs.some(run => run.state === 'running'))).toBe(true)
    await page.getByRole('button', { name: 'Antwort stoppen', exact: true }).click()
    await expect.poll(() => events.some(event => event.type === 'tool.cancelled')).toBe(true)
    await expect(page.locator('.message-assistant').last()).toHaveAttribute('data-status', 'cancelled')
    events.length = 0
    await page.reload()
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    await expect.poll(() => events.some(event => event.type === 'tool.snapshot' && event.runs.some(run => run.state === 'cancelled'))).toBe(true)
    await composer.fill('/p2-error')
    await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
    await composer.press('Enter')
    await expect.poll(() => events.some(event => event.type === 'tool.failed' && event.payload.errorCode === 'PROVIDER_ERROR')).toBe(true)
    await expect(page.locator('.message-assistant').last()).toHaveAttribute('data-status', 'completed')
  })
}
