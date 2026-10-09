import { defineConfig, devices } from '@playwright/test'

const backendPort = Number(process.env.NORIS_E2E_BACKEND_PORT ?? 8000)
const frontendPort = Number(process.env.NORIS_E2E_FRONTEND_PORT ?? 3000)

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  snapshotPathTemplate: '{testDir}/__screenshots__/{platform}/{projectName}/{arg}{ext}',
  expect: { toHaveScreenshot: { maxDiffPixelRatio: 0.001 } },
  use: { baseURL: `http://127.0.0.1:${frontendPort}`, trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', testIgnore: '**/reference-mobile.spec.ts', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', testIgnore: '**/reference-desktop.spec.ts', use: { ...devices['Pixel 7'] } },
  ],
  webServer: [
    {
      command: `uv run --directory ../backend --locked uvicorn noris_ai.main:app --host 127.0.0.1 --port ${backendPort}`,
      url: `http://127.0.0.1:${backendPort}/api/v1/health/ready`,
      reuseExistingServer: false,
      timeout: 30_000,
      env: { NORIS_LLM_PROVIDER: 'disabled', NORIS_LLM_MODELS: '[]' },
    },
    {
      command: 'node node_modules/nuxt/bin/nuxt.mjs build && node ../scripts/serve-browser-fixture.mjs',
      url: `http://127.0.0.1:${frontendPort}`,
      reuseExistingServer: false,
      timeout: 180_000,
      env: { NUXT_PUBLIC_CHAT_TRANSPORT: 'mock', NORIS_E2E_BACKEND_PORT: String(backendPort), NORIS_E2E_FRONTEND_PORT: String(frontendPort), NORIS_NUXT_BUILD_DIR: '.nuxt-e2e', NUXT_TELEMETRY_DISABLED: '1' },
    },
  ],
})
