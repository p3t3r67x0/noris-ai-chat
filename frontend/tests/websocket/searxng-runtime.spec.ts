import { expect, test } from '@playwright/test'
import { clearTestConversations } from './chat-fixtures'
import { validateToolEvent } from '../../app/lib/chat/toolEvents'
import type { ToolWsEvent } from '../../app/lib/chat/toolEvents'

test.skip(Boolean(process.env.NORIS_E2E_COMPOSE_URL), 'Die lokale Testorchestrierung benötigt die explizite Tool-Testfixture')

test.beforeEach(async ({ request }) => {
  await clearTestConversations(request)
  await request.put('/api/v1/chat/drafts/new', { data: { content: '' } })
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null, modelId: null } })
})

for (const theme of ['light', 'dark'] as const) {
  test(`P6: persistierte Lifecycle-Reihenfolge und Empfangslatenz (${theme})`, async ({ page, request }) => {
    const events: ToolWsEvent[] = []
    const received = new Map<string, number>()
    page.on('websocket', socket => socket.on('framereceived', frame => {
      const value: unknown = JSON.parse(String(frame.payload))
      if (validateToolEvent(value)) {
        events.push(value)
        if (value.type === 'tool.completed') received.set(value.runId, Date.now())
      }
    }))
    await page.addInitScript((preference) => { localStorage.setItem('noris-ai-theme', preference) }, theme)
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    const measurements: number[] = []
    for (let i = 0; i < 3; i++) {
      if (i > 0) {
        await page.getByRole('button', { name: 'Neuer Chat', exact: true }).click()
        await expect(page.locator('.message-assistant')).toHaveCount(0)
      }
      events.length = 0
      const composer = page.getByRole('textbox', { name: 'Nachricht', exact: true })
      await composer.fill(`/p6-search-${i}`)
      await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
      await page.getByRole('button', { name: 'Nachricht senden', exact: true }).click()
      await expect(page.locator('.message-user')).toHaveCount(1)
      await expect(page.locator('.message-assistant')).toHaveCount(1)
      await expect(page.locator('.message-assistant').last()).toHaveAttribute('data-status', 'completed')
      // The tool terminal precedes the parent chat terminal. Wait for the
      // current chat to release its send control before starting another chat.
      await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeVisible()
      await expect.poll(() => received.size).toBe(i + 1)
      const terminal = events.find(event => event.type === 'tool.completed')
      if (!terminal || terminal.type === 'tool.snapshot') throw new Error('Suchabschluss fehlt')
      const lifecycle = events.filter(event => event.type !== 'tool.snapshot' && event.runId === terminal.runId)
      expect(lifecycle.map(event => event.type)).toEqual(['tool.progress', 'tool.started', 'tool.result', 'tool.completed'])
      const state = await (await request.get('/api/v1/fixture/search-state')).json()
      measurements.push(received.get(terminal.runId)! - state.committedAt[terminal.runId])
      expect(state.active).toBe(0)
    }
    console.info(`P6_COMMIT_TO_EVENT_MS=${JSON.stringify(measurements)}`)
  })

  for (const submission of ['keyboard', 'button'] as const) {
    test(`P6: HTTP-Suche, Offlineabschluss und wiederholtes Replay (${theme}, ${submission})`, async ({ page, request }) => {
      const events: ToolWsEvent[] = []
      page.on('websocket', socket => socket.on('framereceived', frame => {
        const value: unknown = JSON.parse(String(frame.payload))
        if (validateToolEvent(value)) events.push(value)
      }))
      await page.addInitScript((preference) => { localStorage.setItem('noris-ai-theme', preference) }, theme)
      const before = await (await request.get('/api/v1/fixture/search-state')).json()
      await page.goto('/')
      await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      const composer = page.getByRole('textbox', { name: 'Nachricht', exact: true })
      await composer.fill('/p6-slow')
      await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
      if (submission === 'keyboard') await composer.press('Enter')
      else await page.getByRole('button', { name: 'Nachricht senden', exact: true }).click()
      await expect(page.locator('.message-user')).toHaveCount(1)
      await expect.poll(() => events.some(event => event.type === 'tool.started')).toBe(true)
      const started = events.find(event => event.type === 'tool.started')
      if (!started || started.type === 'tool.snapshot') throw new Error('Persistierter Suchlauf fehlt')
      await page.goto('about:blank')
      await expect.poll(async () => (await (await request.get(`/api/v1/chat/tool-runs/${started.runId}`)).json()).run.state).toBe('succeeded')
      for (let i = 0; i < 3; i++) {
        events.length = 0
        await page.goto('/')
        await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
        await expect.poll(() => events.some(event => event.type === 'tool.snapshot'
          && event.runs.some(run => run.runId === started.runId && run.state === 'succeeded' && run.result?.sourceCount === 5))).toBe(true)
        expect(events.some(event => event.type === 'tool.started')).toBe(false)
        const state = await (await request.get('/api/v1/fixture/search-state')).json()
        expect(state.calls - before.calls).toBe(1)
        await page.goto('about:blank')
      }
      const response = await (await request.get(`/api/v1/chat/tool-runs/${started.runId}`)).json()
      expect(response.latestResult.provider).toBe('searxng')
      expect(response.latestResult.sources[0].title).toBe('Quelle')
      expect(response.latestResult.sources[0].snippet).toContain('Ignore previous instructions')
      expect(JSON.stringify(events)).not.toContain('Ignore previous instructions')
    })

    test(`P6: sichere Fehler und Timeout bleiben nach Reload terminal (${theme}, ${submission})`, async ({ page, request }) => {
      const events: ToolWsEvent[] = []
      page.on('websocket', socket => socket.on('framereceived', frame => {
        const value: unknown = JSON.parse(String(frame.payload))
        if (validateToolEvent(value)) events.push(value)
      }))
      await page.addInitScript((preference) => { localStorage.setItem('noris-ai-theme', preference) }, theme)
      await page.goto('/')
      await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      for (const [prompt, type, state, code] of [
        ['/p6-error', 'tool.failed', 'failed', 'PROVIDER_ERROR'],
        ['/p6-timeout', 'tool.timed_out', 'timed_out', 'TOOL_TIMEOUT'],
      ] as const) {
        if (prompt === '/p6-timeout') {
          await page.getByRole('button', { name: 'Neuer Chat', exact: true }).click()
          await expect(page.locator('.message-assistant')).toHaveCount(0)
        }
        const composer = page.getByRole('textbox', { name: 'Nachricht', exact: true })
        await composer.fill(prompt)
        await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
        if (submission === 'keyboard') await composer.press('Enter')
        else await page.getByRole('button', { name: 'Nachricht senden', exact: true }).click()
        await expect(page.locator('.message-user')).toHaveCount(1)
        await expect.poll(() => events.some(event => event.type === type && event.payload.errorCode === code)).toBe(true)
        const terminal = events.find(event => event.type === type)
        if (!terminal || terminal.type === 'tool.snapshot') throw new Error('Terminales Suchereignis fehlt')
        await expect(page.locator('.message-assistant').last()).toHaveAttribute('data-status', 'completed')
        await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeVisible()
        const response = await (await request.get(`/api/v1/chat/tool-runs/${terminal.runId}`)).json()
        expect(response.run.state).toBe(state)
        expect(response.latestResult).toBeNull()
        events.length = 0
        await page.reload()
        await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
        await expect.poll(() => events.some(event => event.type === 'tool.snapshot'
          && event.runs.some(run => run.runId === terminal.runId && run.state === state))).toBe(true)
        expect(JSON.stringify(events)).not.toContain('upstream-sensitive-body')
      }
    })
  }
}
