import { expect, test } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

test.skip(process.env.NORIS_RUN_LIVE_LLM_SMOKE !== '1', 'Explicit paid opt-in required.')

const model = 'vllm/release/gpt-oss-120b'
const prompt = 'Erkläre in zwei Sätzen, was ein MCP-Server ist.'
const session = process.env.NORIS_LIVE_SESSION
interface Call { ordinal: number, outcome: string, upstream_http_closed: boolean, upstream_socket_closed: boolean | null, text_deltas: number }
const state = (): { calls: Call[] } => {
  if (!session) throw new Error('Local backend observations required for transport acceptance.')
  return JSON.parse(readFileSync(join(session, 'state.json'), 'utf8')) as { calls: Call[] }
}
const record = (file: string, result: object) => { if (session) writeFileSync(join(session, file), JSON.stringify(result), { mode: 0o600 }) }

test.beforeEach(async ({ page }) => {
  test.setTimeout(150_000)
  if (!process.env.NORIS_LIVE_APP_ORIGIN) throw new Error('Application origin missing.')
  const catalog = await page.goto('/api/v1/llm/models')
  expect(catalog?.status()).toBe(200)
  const data = await catalog?.json() as { default_model: string, models: { id: string, max_output_tokens: number }[] }
  expect(data.models.map(item => item.id)).toEqual([model])
  expect(data.default_model).toBe(model)
  expect(data.models[0]?.max_output_tokens).toBe(256) // Reject excess cost before sending.
  await page.addInitScript(() => {
    const original = window.fetch
    window.fetch = (input, init) => {
      if (String(input).endsWith('/api/v1/llm/chat')) init?.signal?.addEventListener('abort', () => { document.documentElement.dataset.liveFetchAborted = 'true' }, { once: true })
      return original(input, init)
    }
  })
  await page.goto('/')
  await expect(page.locator('[data-ready="true"]')).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole('button', { name: 'Modell auswählen', exact: true })).toContainText('GPT-OSS 120B')
})

test('explicitly enabled Noris smoke, focus, anchoring and safe error display', async ({ page }) => {
  await page.getByRole('button', { name: 'Modell auswählen', exact: true }).click()
  await page.getByRole('option', { name: 'GPT-OSS 120B', exact: true }).click()
  await page.evaluate(() => {
    document.documentElement.dataset.liveStreamSeen = 'false'
    const observer = new MutationObserver((mutations) => {
      if (mutations.some(item => item.oldValue === 'streaming' || (item.target as Element).getAttribute('data-generation-status') === 'streaming')) document.documentElement.dataset.liveStreamSeen = 'true'
    })
    observer.observe(document.body, { subtree: true, attributes: true, attributeOldValue: true, attributeFilter: ['data-generation-status'] })
  })
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.fill(prompt)
  const started = Date.now()
  const response = page.waitForResponse(item => item.url().endsWith('/api/v1/llm/chat') && item.request().method() === 'POST')
  await input.press('Enter')
  expect((await response).status()).toBe(200)
  await expect(page.locator('[data-generation-status="completed"], [data-generation-status="failed"]')).toBeAttached({ timeout: 130_000 })
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  const text = await page.locator('.message-assistant .markdown-content').textContent() ?? ''
  const mcp = /mcp/i.test(text)
  expect(mcp).toBe(true) // Boolean assertions never echo provider output.
  await expect(input).toBeFocused()
  await expect(page.locator('html')).toHaveAttribute('data-live-stream-seen', 'true')
  const header = await page.locator('.chat-header').boundingBox()
  const question = await page.locator('.message-user').boundingBox()
  const anchored = Boolean(header && question && question.y >= header.y + header.height && question.y - header.y - header.height < 40)
  expect(anchored).toBe(true)
  const noOverflow = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth && scrollY === 0)
  expect(noOverflow).toBe(true)
  record('browser-result.json', { status: 'PASS', model, app_http_status: 200, total_ms: Date.now() - started, text_characters: text.length, content_mentions_mcp: mcp, streaming_seen: true, input_focused: true, send_anchored: anchored, no_viewport_overflow: noOverflow })

  // Context rejection happens before any provider request; no extra paid call.
  const callsBefore = session ? state().calls.length : null
  await input.fill('ü'.repeat(9000))
  await input.press('Enter')
  await expect(page.locator('[data-generation-status="failed"]')).toBeAttached()
  await expect(page.getByRole('button', { name: 'Erneut versuchen', exact: true })).toBeVisible()
  if (session) expect(state().calls.length).toBe(callsBefore)
  record('browser-error-result.json', { status: 'PASS', scenario: 'CONTEXT_LIMIT', additional_provider_calls: 0 })
})

test('explicit Stop preserves partial text and closes the actual upstream HTTP connection', async ({ page }) => {
  test.skip(process.env.NORIS_LIVE_TEST_STOP !== '1', 'Stop test needs its separately approved paid request.')
  if (!session) throw new Error('Local backend observations required for HTTP-close proof.')
  const before = state().calls.length
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).fill('Zähle die Zahlen von 1 bis 100, jede Zahl in einer eigenen Zeile.')
  const started = Date.now()
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).press('Enter')
  await page.waitForFunction(() => document.querySelector('[data-generation-status="streaming"]') && (document.querySelector('.message-assistant .markdown-content')?.textContent?.length ?? 0) >= 12, undefined, { timeout: 120_000 })
  await page.getByRole('button', { name: 'Antwort stoppen', exact: true }).click()
  await expect(page.locator('[data-generation-status="cancelled"]')).toBeAttached()
  const partial = await page.locator('.message-assistant .markdown-content').textContent() ?? ''
  expect(Boolean(partial)).toBe(true)
  await expect(page.locator('html')).toHaveAttribute('data-live-fetch-aborted', 'true')
  await expect.poll(() => state().calls[before]?.upstream_http_closed).toBe(true)
  const call = state().calls[before]
  expect(call?.outcome).toBe('cancelled')
  expect(call?.upstream_socket_closed).toBe(true)
  const deltas = call?.text_deltas
  await page.waitForTimeout(1000)
  expect((await page.locator('.message-assistant .markdown-content').textContent()) === partial).toBe(true)
  expect(state().calls[before]?.text_deltas).toBe(deltas)
  record('stop-result.json', { status: 'PASS', model, total_ms: Date.now() - started, partial_characters: partial.length, browser_fetch_aborted: true, fastapi_cancelled: true, upstream_http_closed: true, upstream_socket_closed: true, no_late_deltas: true, gpu_abort: 'NOT TESTED', billing_stop: 'NOT TESTED' })
})
