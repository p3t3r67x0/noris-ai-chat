import { expect, test } from '@playwright/test'
import { clearTestConversations, stableModelCatalog } from './chat-fixtures'
import { validateToolEvent } from '../../app/lib/chat/toolEvents'
import type { ToolWsEvent } from '../../app/lib/chat/toolEvents'

test.skip(Boolean(process.env.NORIS_E2E_COMPOSE_URL), 'P7b uses the explicitly selected disposable test orchestrator')

test.beforeEach(async ({ page, request }) => {
  await stableModelCatalog(page)
  await clearTestConversations(request)
  await request.put('/api/v1/chat/drafts/new', { data: { content: '' } })
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null, modelId: null } })
})

for (const theme of ['light', 'dark'] as const) {
  test(`P7b: trusted research uses the existing stream and reload never dispatches (${theme})`, async ({ page, request }) => {
    const events: ToolWsEvent[] = []
    page.on('websocket', socket => socket.on('framereceived', frame => {
      const value: unknown = JSON.parse(String(frame.payload))
      if (validateToolEvent(value)) events.push(value)
    }))
    await page.addInitScript(value => localStorage.setItem('noris-ai-theme', value), theme)
    const before = await (await request.get('/api/v1/fixture/search-state')).json()
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    await page.getByRole('textbox', { name: 'Nachricht', exact: true }).fill('/p7b Latest QGIS developments')
    await page.getByRole('button', { name: 'Nachricht senden', exact: true }).click()
    await expect(page.locator('.message-assistant').last()).toHaveAttribute('data-status', 'completed')
    expect(events.filter(event => event.type === 'tool.completed' && event.payload.toolId === 'web.search.v1')).toHaveLength(1)
    expect(events.filter(event => event.type === 'tool.completed' && event.payload.toolId === 'web.fetch.v1')).toHaveLength(3)
    const after = await (await request.get('/api/v1/fixture/search-state')).json()
    expect(after.calls - before.calls).toBe(1)
    expect(after.fetchCalls - before.fetchCalls).toBe(3)
    expect(JSON.stringify(events)).not.toContain('P7a untrusted source text')
    await page.reload()
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    await expect(page.locator('.message-assistant').last()).toHaveAttribute('data-status', 'completed')
    await expect.poll(() => events.some(event => event.type === 'tool.snapshot'
      && event.runs.some(run => run.toolId === 'web.fetch.v1' && run.state === 'succeeded'))).toBe(true)
    const reloaded = await (await request.get('/api/v1/fixture/search-state')).json()
    expect(reloaded.calls).toBe(after.calls)
    expect(reloaded.fetchCalls).toBe(after.fetchCalls)
  })
}
