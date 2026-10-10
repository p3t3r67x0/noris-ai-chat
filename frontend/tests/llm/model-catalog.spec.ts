import { expect, test } from '@playwright/test'

const fixtureOrigin = `http://127.0.0.1:${Number(process.env.NORIS_E2E_PROVIDER_PORT ?? 8591)}`
const ids = ['fixture-alpha', 'fixture-beta']

test.beforeEach(async ({ page, request }) => {
  await request.post(`${fixtureOrigin}/fixture/catalog`, { data: { ids } })
  await expect.poll(async () => {
    const response = await request.get('/api/v1/llm/models')
    const catalog = await response.json() as { models: { id: string }[] }
    return catalog.models.map(model => model.id)
  }).toEqual(ids)
  await page.goto('/api/v1/llm/models')
  await page.goto('/')
  await expect(page.locator('[data-ready="true"]')).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole('button', { name: 'Modell auswählen', exact: true })).toContainText('Fixture Alpha')
})

test.afterEach(async ({ request }) => {
  await request.post(`${fixtureOrigin}/fixture/catalog`, { data: { ids } })
})

test('keyboard selection synchronizes the composer, preserves drafts and survives reload', async ({ page }, info) => {
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.fill('Entwurf bleibt erhalten')
  const menu = page.getByRole('button', { name: 'Modell auswählen', exact: true })
  await menu.focus()
  await menu.press('Enter')
  await expect(page.getByRole('option', { name: 'Fixture Beta' })).toBeVisible()
  await page.keyboard.press('End')
  await page.keyboard.press('Enter')
  await expect(menu).toContainText('Fixture Beta')
  if (info.project.name === 'desktop') await expect(page.getByRole('button', { name: 'Modell im Eingabefeld auswählen' })).toContainText('Fixture Beta')
  await expect(input).toHaveValue('Entwurf bleibt erhalten')
  await expect(page.locator('.chat-message')).toHaveCount(0)
  await page.reload()
  await expect(menu).toContainText('Fixture Beta')
  await expect(input).toHaveValue('Entwurf bleibt erhalten')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('revocation preserves messages and draft until an explicit fallback choice', async ({ page, request }) => {
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.fill('Gespräch bleibt erhalten')
  await input.press('Enter')
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  await input.fill('Nächster Entwurf')
  const before = await request.get(`${fixtureOrigin}/fixture/state`).then(response => response.json()) as { calls: unknown[] }
  await request.post(`${fixtureOrigin}/fixture/catalog`, { data: { ids: ['fixture-beta'] } })
  await expect(page.getByText('Dein gewähltes Modell ist nicht mehr verfügbar.', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeDisabled()
  await expect(input).toHaveValue('Nächster Entwurf')
  await expect(page.locator('.chat-content')).toContainText('HTTP-Antwort')
  await page.getByRole('button', { name: 'Verfügbares Modell auswählen' }).click()
  await expect(page.getByRole('button', { name: 'Modell auswählen', exact: true })).toContainText('Fixture Beta')
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
  const after = await request.get(`${fixtureOrigin}/fixture/state`).then(response => response.json()) as { calls: unknown[] }
  expect(after.calls).toHaveLength(before.calls.length)
})

test('discovery failures and empty catalogs block sending without damaging drafts', async ({ page, request }) => {
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.fill('Privater synthetischer Entwurf')
  await request.post(`${fixtureOrigin}/fixture/catalog`, { data: { ids: [], status: 503 } })
  await expect(page.getByRole('button', { name: 'Modelle neu laden' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeDisabled()
  await expect(input).toHaveValue('Privater synthetischer Entwurf')
  await request.post(`${fixtureOrigin}/fixture/catalog`, { data: { ids: [] } })
  await expect.poll(async () => (await request.get('/api/v1/llm/models')).status()).toBe(200)
  await page.getByRole('button', { name: 'Modelle neu laden' }).click()
  await expect(page.getByText('Für diesen Zugang sind derzeit keine Chatmodelle verfügbar.')).toBeVisible()
  await expect(input).toHaveValue('Privater synthetischer Entwurf')
})

test('documented models are grouped and the entitled router is first', async ({ page, request }) => {
  await request.post(`${fixtureOrigin}/fixture/catalog`, { data: { ids: [
    'smart_router', 'vllm/release/gpt-oss-120b', 'vllm/release/glm-5-2',
    'vllm/release/gemma-4-31b-it', 'vllm/release/qwen3.6-27b',
    'vllm/release/harrier-oss-v1-0.6b', 'vllm/release/bge-reranker-v2-m3', 'unknown-model',
  ] } })
  await expect.poll(async () => {
    const response = await request.get('/api/v1/llm/models')
    return (await response.json() as { models: { id: string }[] }).models[0]?.id
  }).toBe('smart_router')
  await page.reload()
  // The prior preference remains unavailable until the user chooses the offered fallback.
  await page.getByRole('button', { name: 'Verfügbares Modell auswählen' }).click()
  const menu = page.getByRole('button', { name: 'Modell auswählen', exact: true })
  await expect(menu).toContainText('Automatisch')
  await menu.click()
  await expect(page.getByRole('option').first()).toContainText('Automatisch')
  await expect(page.getByText('Reasoning & Entwicklung', { exact: true })).toBeVisible()
  await expect(page.getByRole('option', { name: 'GPT-OSS 120B', exact: false })).toBeVisible()
  await expect(page.getByRole('option', { name: 'Qwen3.6 27B', exact: false })).toBeVisible()
  await expect(page.getByRole('option', { name: /Harrier|Reranker|unknown-model/ })).toHaveCount(0)
  await expect(page.getByText('Bei „Automatisch“ kann das tatsächliche Modell je nach Anfrage wechseln.')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})


test('native 2.4 catalogs include new approved models with dated USD quotes', async ({ page, request }) => {
  const chatIds = [
    'vllm/qsu/deepseek-v41-flash', 'vllm/qsu/glm-5-3-flash', 'vllm/qsu/qwen3.8-27b',
    'vllm/release/gemma-4-31b-it', 'vllm/release/glm-5-2', 'vllm/release/gpt-oss-120b', 'vllm/release/qwen3.6-27b',
  ]
  await request.post(`${fixtureOrigin}/fixture/catalog`, { data: { ids: [
    ...chatIds, 'vllm/release/harrier-oss-v1-0.6b', 'vllm/release/bge-reranker-v2-m3',
    'vllm/release/jina-reranker-v2-base-multilingual', 'unknown-model',
  ] } })
  await expect.poll(async () => {
    const catalog = await request.get('/api/v1/llm/models').then(response => response.json()) as { models: { id: string }[] }
    return catalog.models.map(model => model.id).sort()
  }).toEqual([...chatIds].sort())
  await page.reload()
  await page.getByRole('button', { name: 'Verfügbares Modell auswählen' }).click()
  const menu = page.getByRole('button', { name: 'Modell auswählen', exact: true })
  await expect(menu).toContainText('DeepSeek V4.1 Flash')
  await menu.click()
  const deepseek = page.getByRole('option', { name: 'DeepSeek V4.1 Flash', exact: false })
  await expect(deepseek).toContainText('1.048.576 Tokens Kontext')
  await expect(deepseek).toContainText('10 / 30 USD je Mio.')
  await expect(deepseek).toContainText('2 USD Cache-Eingabe')
  await expect(deepseek).toContainText('Abruf')
  await expect(page.getByRole('option', { name: 'Qwen3.8 27B', exact: false })).toBeAttached()
  await expect(page.getByRole('option', { name: /Harrier|Reranker|unknown-model|Automatisch/ })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})
