import { expect, test } from '@playwright/test'

test('frontend reaches the real backend and PostgreSQL through the same origin', async ({ page }) => {
  const readiness = page.waitForResponse('/api/v1/health/ready')
  await page.goto('/status')
  expect((await readiness).status()).toBe(200)
  await expect(page.getByRole('heading', { name: 'noris AI' })).toBeVisible()
  await expect(page.getByRole('status')).toHaveText('Dienst verfügbar')
  await page.reload()
  await expect(page.getByRole('status')).toHaveText('Dienst verfügbar')
})

test('dependency failure is recoverable using the keyboard', async ({ page }) => {
  await page.route('**/api/v1/health/ready', route => route.fulfill({
    status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'NOT_READY' } }),
  }))
  await page.goto('/status')
  await expect(page.getByRole('status')).toHaveText('Dienst derzeit nicht erreichbar')
  await page.unroute('**/api/v1/health/ready')
  await page.getByRole('button', { name: 'Verbindung prüfen' }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('status')).toHaveText('Dienst verfügbar')
})

test('the foundation page fits the viewport', async ({ page }) => {
  await page.goto('/status')
  await expect(page.getByRole('status')).toHaveText('Dienst verfügbar')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})
