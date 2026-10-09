import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { CHAT_STORAGE_KEY } from '../../app/lib/chat/persistence'
import type { ConversationTitleRequest } from '../../app/lib/chat/types'

const fixtureOrigin = `http://127.0.0.1:${Number(process.env.NORIS_E2E_PROVIDER_PORT ?? 8591)}`

async function sidebar(page: Page) {
  const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  await expect(page.getByRole('navigation', { name: 'Gespräche' })).toBeVisible()
}
async function send(page: Page, text: string) {
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).fill(text)
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).press('Enter')
}
test.beforeEach(async ({ page }) => {
  await page.goto('/api/v1/llm/models')
  await page.goto('/')
  await expect(page.locator('[data-ready="true"]')).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole('button', { name: 'Modell auswählen', exact: true })).toContainText('Fixture Alpha')
})

test('real transport starts chat first, posts only the first message and persists the returned title', async ({ page, request }) => {
  const order: string[] = []
  let payload: ConversationTitleRequest | undefined
  page.on('request', req => {
    if (req.url().endsWith('/llm/chat')) order.push('chat')
    if (req.url().endsWith('/llm/conversation-title')) { order.push('title'); payload = req.postDataJSON() as ConversationTitleRequest }
  })
  await send(page, 'Welche Vorteile bietet Rust gegenüber C++?')
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  await sidebar(page)
  await expect(page.getByRole('navigation', { name: 'Gespräche' }).getByRole('button', { name: 'Rust vs. C++', exact: true })).toBeVisible()
  expect(order).toEqual(['chat', 'title'])
  expect(payload).toMatchObject({ firstMessage: 'Welche Vorteile bietet Rust gegenüber C++?', modelId: 'fixture-alpha' })
  expect(Object.keys(payload!).sort()).toEqual(['conversationId', 'firstMessage', 'inputMessageId', 'modelId'])
  const state = await request.get(`${fixtureOrigin}/fixture/state`).then(response => response.json()) as { title_calls: { max_tokens: number, messages: { role: string, content: string }[] }[] }
  expect(state.title_calls.some(call => call.max_tokens === 96 && call.messages[0]?.role === 'system' && call.messages[1]?.content === payload!.firstMessage)).toBe(true)
  await page.reload()
  await expect(page.locator('[data-ready="true"]')).toBeVisible()
  await sidebar(page)
  await expect(page.getByRole('navigation', { name: 'Gespräche' }).getByRole('button', { name: 'Rust vs. C++', exact: true })).toHaveAttribute('aria-current', 'page')
  expect(order).toEqual(['chat', 'title'])
})

test('a late backend title cannot overwrite a manual rename', async ({ page }) => {
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  let arrived!: () => void
  const pending = new Promise<void>(resolve => { arrived = resolve })
  await page.route('**/api/v1/llm/conversation-title', async route => { arrived(); await gate; await route.continue() })
  await send(page, 'Warum funktioniert Docker DNS nicht?')
  await pending
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  await sidebar(page)
  await page.getByRole('button', { name: 'Aktionen für Neuer Chat' }).click()
  await page.getByRole('menuitem', { name: 'Umbenennen' }).click()
  await page.getByRole('textbox', { name: 'Chat-Titel' }).fill('Meine DNS-Notizen')
  await page.getByRole('textbox', { name: 'Chat-Titel' }).press('Enter')
  const response = page.waitForResponse('**/api/v1/llm/conversation-title')
  release()
  expect((await response).status()).toBe(200)
  await sidebar(page)
  await expect(page.getByRole('navigation', { name: 'Gespräche' }).getByRole('button', { name: 'Meine DNS-Notizen', exact: true })).toBeVisible()
  await expect.poll(async () => await page.evaluate(key => Object.values(JSON.parse(localStorage.getItem(key)!).conversations.conversations).map(item => (item as { titleSource: string }).titleSource), CHAT_STORAGE_KEY)).toEqual(['manual'])
})

for (const scenario of ['invalid', 'timeout', 'error'] as const) {
  test(`title ${scenario} leaves a usable fallback without retry after reload`, async ({ page }) => {
    let attempts = 0
    page.on('request', request => { if (request.url().endsWith('/llm/conversation-title')) attempts++ })
    const result = page.waitForResponse('**/api/v1/llm/conversation-title')
    await send(page, `/title-${scenario}`)
    await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
    const response = await result
    expect(response.ok()).toBe(false)
    expect((await response.json() as { error: { code: string } }).error.code).toBe(({ invalid: 'INVALID_RESPONSE', timeout: 'TIMEOUT', error: 'RATE_LIMIT' })[scenario])
    await sidebar(page)
    await expect(page.getByRole('navigation', { name: 'Gespräche' }).getByRole('button', { name: 'Neuer Chat', exact: true })).toHaveAttribute('aria-current', 'page')
    await page.reload()
    await expect(page.locator('[data-ready="true"]')).toBeVisible()
    const saved = await page.evaluate(key => Object.values(JSON.parse(localStorage.getItem(key)!).conversations.conversations).map(item => { const record = item as { titleSource: string, titleGenerationAttempted: boolean }; return [record.titleSource, record.titleGenerationAttempted] }), CHAT_STORAGE_KEY)
    expect(saved).toEqual([['fallback', true]])
    expect(attempts).toBe(1)
  })
}

test('deletion closes a pending title request and never restores the conversation', async ({ page, request }) => {
  const before = await request.get(`${fixtureOrigin}/fixture/state`).then(response => response.json()) as { title_cancelled: number }
  const started = page.waitForRequest('**/api/v1/llm/conversation-title')
  await send(page, '/title-timeout delete')
  await started
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  await sidebar(page)
  await page.getByRole('button', { name: 'Aktionen für Neuer Chat' }).click()
  await page.getByRole('menuitem', { name: 'Löschen', exact: true }).click()
  await page.getByRole('dialog', { name: 'Chat löschen?' }).getByRole('button', { name: 'Chat löschen', exact: true }).click()
  await expect.poll(async () => (await request.get(`${fixtureOrigin}/fixture/state`).then(response => response.json()) as { title_cancelled: number }).title_cancelled).toBeGreaterThan(before.title_cancelled)
  await sidebar(page)
  await expect(page.locator('.conversation-row')).toHaveCount(0)
  await expect.poll(async () => await page.evaluate(key => Object.keys(JSON.parse(localStorage.getItem(key)!).conversations.conversations), CHAT_STORAGE_KEY)).toEqual([])
})
