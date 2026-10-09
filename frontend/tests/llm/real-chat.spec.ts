import { expect, test } from '@playwright/test'

const fixtureOrigin = `http://127.0.0.1:${Number(process.env.NORIS_E2E_PROVIDER_PORT ?? 8591)}`

test.beforeEach(async ({ page }) => {
  await page.goto('/api/v1/llm/models')
  await page.goto('/')
  await expect(page.locator('[data-ready="true"]')).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole('button', { name: 'Modell auswählen', exact: true })).toContainText('Fixture Alpha')
})

test('streams real HTTP text through the existing chat state', async ({ page }) => {
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).fill('Hallo HTTP')
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).press('Enter')
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  await expect(page.locator('.chat-content')).toContainText('HTTP-Antwort mit Grüße 🌍.')
})

test('Stop closes a quiet provider stream', async ({ page, request }, info) => {
  const before = await request.get(`${fixtureOrigin}/fixture/state`).then(response => response.json()) as { cancelled: number }
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).fill(`/quiet ${info.project.name}`)
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).press('Enter')
  await expect(page.getByRole('button', { name: 'Antwort stoppen', exact: true })).toBeVisible()
  await expect.poll(async () => {
    const state = await request.get(`${fixtureOrigin}/fixture/state`).then(response => response.json()) as { calls: { messages: { content: string }[] }[] }
    return state.calls.some(call => call.messages.at(-1)?.content === `/quiet ${info.project.name}`)
  }).toBe(true)
  await page.getByRole('button', { name: 'Antwort stoppen', exact: true }).click()
  await expect(page.locator('[data-generation-status="cancelled"]')).toBeAttached()
  await expect.poll(async () => (await request.get(`${fixtureOrigin}/fixture/state`).then(response => response.json()) as { cancelled: number }).cancelled).toBeGreaterThan(before.cancelled)
  const continuation = `Weiter nach Stop ${info.project.name}`
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).fill(continuation)
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).press('Enter')
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  const state = await request.get(`${fixtureOrigin}/fixture/state`).then(response => response.json()) as { calls: { messages: { role: string, content: string }[] }[] }
  expect(state.calls.find(call => call.messages.at(-1)?.content === continuation)?.messages).toEqual([
    { role: 'user', content: `/quiet ${info.project.name}` },
    { role: 'assistant', content: '' },
    { role: 'user', content: continuation },
  ])
})

test('Retry and model switching keep only the original active path', async ({ page, request }, info) => {
  const prompt = `/retry ${info.project.name}`
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).fill(prompt)
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).press('Enter')
  await expect(page.locator('[data-generation-status="failed"]')).toBeAttached()
  await page.getByRole('button', { name: 'Modell auswählen', exact: true }).click()
  await page.getByRole('option', { name: 'Fixture Beta' }).click()
  await page.getByRole('button', { name: 'Erneut versuchen', exact: true }).click()
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  const state = await request.get(`${fixtureOrigin}/fixture/state`).then(response => response.json()) as { calls: { model: string, messages: { role: string, content: string }[] }[] }
  const calls = state.calls.filter(call => call.messages.at(-1)?.content === prompt)
  expect(calls).toHaveLength(2)
  expect(calls[1]?.model).toBe('fixture-beta')
  expect(calls[1]?.messages).toEqual([{ role: 'user', content: prompt }])
})
