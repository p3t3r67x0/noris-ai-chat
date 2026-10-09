import { expect, test } from '@playwright/test'

test.skip(process.env.NORIS_RUN_LIVE_LLM_SMOKE !== '1', 'Live provider smoke needs explicit opt-in and provisioned credentials.')

test('explicitly enabled live Noris provider smoke through browser and backend', async ({ page }) => {
  const origin = process.env.NORIS_LIVE_APP_ORIGIN
  if (!origin || !process.env.NORIS_LLM_ACCESS_USERNAME || !process.env.NORIS_LLM_ACCESS_PASSWORD) throw new Error('Configure the deployed application origin and application access credentials.')
  test.setTimeout(150_000)
  const catalog = await page.goto('/api/v1/llm/models')
  expect(catalog?.status()).toBe(200)
  await page.goto('/')
  await expect(page.locator('[data-ready="true"]')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Modell auswählen', exact: true })).toHaveText(/\S/)
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).fill('Antworte mit einem kurzen deutschen Gruß.')
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).press('Enter')
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached({ timeout: 130_000 })
  await expect(page.locator('.message-assistant .assistant-content')).not.toBeEmpty()
})
