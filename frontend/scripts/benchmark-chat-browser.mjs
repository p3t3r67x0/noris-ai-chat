// Loopback-only browser measurements against shipped before/after builds.
import { chromium } from '@playwright/test'
import { writeFile } from 'node:fs/promises'

const [url, backend, mode, countRaw, output] = process.argv.slice(2)
const count = Number(countRaw)
if (!url?.startsWith('http://127.0.0.1:') || !backend?.startsWith('http://127.0.0.1:') || !['before', 'after'].includes(mode ?? '') || ![100, 1000, 10000].includes(count) || !output) throw new Error('Expected loopback frontend/backend, before|after, count, output')
const browser = await chromium.launch({ args: ['--enable-precise-memory-info'] })
try {
  const page = await browser.newPage({ httpCredentials: { username: 'fixture-user', password: 'fixture-application-password-never-real' } })
  const metrics = await fetch(`${backend}/fixture/metrics`).then(response => response.json())
  const client = await page.context().newCDPSession(page)
  await client.send('Performance.enable')
  let concurrent = 0
  let maximum = 0
  let requests = 0
  let bytes = 0
  /** @type {string[]} */
  const failures = []
  /** @type {Set<import('@playwright/test').Request>} */
  const tracked = new Set()
  /** @param {import('@playwright/test').Request} request */
  const matches = request => /\/api\/v1\/(conversations|chat\/(preferences|drafts))/.test(request.url())
  page.on('request', request => {
    if (!matches(request)) return
    tracked.add(request); requests++; concurrent++; maximum = Math.max(maximum, concurrent)
  })
  page.on('requestfinished', async request => {
    if (!tracked.delete(request)) return
    concurrent--
    try { bytes += (await request.sizes()).responseBodySize } catch { /* Failure is counted separately. */ }
  })
  page.on('requestfailed', request => {
    if (!tracked.delete(request)) return
    concurrent--; failures.push(request.failure()?.errorText ?? 'failed')
  })
  const start = performance.now()
  await page.goto(url)
  let sidebarMs = null
  let loadMs = null
  let status = 'PASS'
  try {
    await page.locator('[data-conversation-id]').first().waitFor({ timeout: 35000 })
    sidebarMs = performance.now() - start
    await page.waitForFunction(expected => document.querySelectorAll('[data-message-id]').length === expected, mode === 'before' ? 1000 : 50, { timeout: 35000 })
    loadMs = performance.now() - start
  }
  catch { status = 'FAIL' }
  const heap = (await client.send('Performance.getMetrics')).metrics.find(metric => metric.name === 'JSHeapUsedSize')?.value ?? null
  const sql = await fetch(`${backend}/fixture/metrics`).then(response => response.json())
  const failureCounts = Object.fromEntries([...new Set(failures)].map(error => [error, failures.filter(value => value === error).length]))
  const result = { mode, conversations: count, status, sidebar_interactive_ms: sidebarMs && Math.round(sidebarMs), active_window_visible_ms: loadMs && Math.round(loadMs), api_requests: requests, maximum_concurrent_api_requests: maximum, api_response_bytes: bytes, sql_queries: sql.queries - metrics.queries, js_heap_used_bytes: heap, rendered_sidebar_rows: await page.locator('[data-conversation-id]').count(), rendered_messages: await page.locator('[data-message-id]').count(), failure_counts: failureCounts }
  await writeFile(output, JSON.stringify(result, null, 2) + '\n')
  console.log(JSON.stringify(result))
}
finally { await browser.close() }
