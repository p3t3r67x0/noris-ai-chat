import { expect, test } from '@playwright/test'
import { clearTestConversations, stableModelCatalog } from './chat-fixtures'
import { validateToolEvent } from '../../app/lib/chat/toolEvents'
import type { ToolWsEvent } from '../../app/lib/chat/toolEvents'

test.skip(Boolean(process.env.NORIS_E2E_COMPOSE_URL), 'P7a uses the explicitly selected local tool fixture')

test.beforeEach(async ({ page, request }) => {
  await stableModelCatalog(page)
  await clearTestConversations(request)
  await request.put('/api/v1/chat/drafts/new', { data: { content: '' } })
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null, modelId: null } })
})

test('P7a: explicit catalog refresh still blocks dispatch and preserves the draft', async ({ page, request }) => {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  const send = page.getByRole('button', { name: 'Nachricht senden', exact: true })
  await input.fill('/p7a-fetch')
  await expect(send).toBeEnabled()
  const before = await (await request.get('/api/v1/fixture/search-state')).json()
  let release!: () => void
  const pending = new Promise<void>((resolve) => { release = resolve })
  await page.route('**/api/v1/llm/models', async (route) => {
    await pending
    await route.fallback()
  })
  try {
    await page.evaluate(() => window.dispatchEvent(new Event('focus')))
    await expect(send).toBeDisabled()
    await input.press('Enter')
    await expect(input).toHaveValue('/p7a-fetch')
    await expect(page.locator('.message-user')).toHaveCount(0)
    const blocked = await (await request.get('/api/v1/fixture/search-state')).json()
    expect(blocked.calls).toBe(before.calls)
    expect(blocked.fetchCalls).toBe(before.fetchCalls)
  }
  finally {
    release()
  }
  await expect(send).toBeEnabled()
  await input.press('Enter')
  await expect(page.locator('.message-assistant').last()).toHaveAttribute('data-status', 'completed')
  const after = await (await request.get('/api/v1/fixture/search-state')).json()
  expect(after.calls - before.calls).toBe(1)
  expect(after.fetchCalls - before.fetchCalls).toBe(1)
})

for (const theme of ['light', 'dark'] as const) {
  test(`P7a: fetch lifecycle, private text and reconnect without download (${theme})`, async ({ page, request }) => {
    const events: ToolWsEvent[] = []
    page.on('websocket', socket => socket.on('framereceived', frame => {
      const value: unknown = JSON.parse(String(frame.payload))
      if (validateToolEvent(value)) events.push(value)
    }))
    await page.addInitScript(preference => localStorage.setItem('noris-ai-theme', preference), theme)
    const before = await (await request.get('/api/v1/fixture/search-state')).json()
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    await page.getByRole('textbox', { name: 'Nachricht', exact: true }).fill('/p7a-fetch')
    await page.getByRole('button', { name: 'Nachricht senden', exact: true }).click()
    await expect.poll(() => events.some(event => event.type === 'tool.completed'
      && event.payload.toolId === 'web.fetch.v1')).toBe(true)
    const terminal = events.find(event => event.type === 'tool.completed' && event.payload.toolId === 'web.fetch.v1')
    if (!terminal || terminal.type === 'tool.snapshot') throw new Error('Fetch completion missing')
    expect(events.filter(event => event.type !== 'tool.snapshot' && event.runId === terminal.runId)
      .map(event => event.type)).toEqual(['tool.progress', 'tool.started', 'tool.result', 'tool.completed'])
    expect(JSON.stringify(events)).not.toContain('P7a untrusted source text.')
    const result = await request.get(`/api/v1/chat/tool-runs/${terminal.runId}`)
    expect(result.status()).toBe(200)
    const saved = await result.json()
    expect(saved.latestResult.text).toBe('P7a untrusted source text.')
    expect(saved.latestResult.digest).toMatch(/^[0-9a-f]{64}$/)
    await expect(page.locator('.message-assistant').last()).toHaveAttribute('data-status', 'completed')
    for (let i = 0; i < 3; i++) {
      events.length = 0
      await page.reload()
      await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      await expect.poll(() => events.some(event => event.type === 'tool.snapshot'
        && event.runs.some(run => run.runId === terminal.runId && run.state === 'succeeded'))).toBe(true)
      expect(events.some(event => event.type === 'tool.started')).toBe(false)
      expect(JSON.stringify(events)).not.toContain('P7a untrusted source text.')
      const state = await (await request.get('/api/v1/fixture/search-state')).json()
      expect(state.fetchCalls - before.fetchCalls).toBe(1)
    }
  })
}
