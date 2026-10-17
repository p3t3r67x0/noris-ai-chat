import { expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import { mkdir } from 'node:fs/promises'
import { notificationBackend, conversationId } from '../notifications/fixtures'
import { loadingGate } from '../websocket/loading-fixtures'

const stage = process.env.NORIS_LOADING_CAPTURE_STAGE ?? 'after'
if (!['before', 'after'].includes(stage)) throw new Error('Capture stage must be before or after')
const evidence = fileURLToPath(new URL('../../../docs/ui-reference/loading-spinner', import.meta.url))

test('capture a synthetic pending conversation at the identical viewport and DPR', async ({ page }) => {
  test.setTimeout(60_000)
  await notificationBackend(page)
  await page.addInitScript(() => { localStorage.setItem('noris-ai-theme', 'light'); localStorage.setItem('noris-ai:sidebar-open', 'true') })
  const gate = loadingGate()
  const hit = loadingGate()
  await page.route(`**/api/v1/conversations/${conversationId}/active-path?*`, async route => { hit.release(); await gate.promise; await route.fallback() })
  await page.goto('/')
  await hit.promise
  await page.evaluate(() => document.fonts.ready)
  if (stage === 'after') await expect(page.getByRole('status', { name: 'Chat wird geladen', exact: true })).toBeVisible()
  await mkdir(evidence, { recursive: true })
  await page.screenshot({ path: resolve(evidence, `loading-${stage}.png`), animations: 'disabled', caret: 'hide' })
  gate.release()
  await expect(page.locator('.message-assistant').first()).toBeVisible()
})
