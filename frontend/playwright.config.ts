import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: { baseURL: 'http://127.0.0.1:3000', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  webServer: [
    {
      command: 'uv run --directory ../backend --locked uvicorn noris_ai.main:app --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/api/v1/health/ready',
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: 'pnpm dev --host 127.0.0.1 --port 3000',
      url: 'http://127.0.0.1:3000',
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
