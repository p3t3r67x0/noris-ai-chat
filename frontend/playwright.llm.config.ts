import { defineConfig, devices } from '@playwright/test'

const providerPort = Number(process.env.NORIS_E2E_PROVIDER_PORT ?? 8591)
const backendPort = Number(process.env.NORIS_E2E_BACKEND_PORT ?? 8592)
const frontendPort = Number(process.env.NORIS_E2E_FRONTEND_PORT ?? 8593)

export default defineConfig({
  testDir: './tests/llm',
  outputDir: './test-results/llm',
  snapshotPathTemplate: '{testDir}/__screenshots__/{platform}/{projectName}/{arg}{ext}',
  expect: { toHaveScreenshot: { maxDiffPixelRatio: 0.001 } },
  workers: 1, retries: 0,
  use: { baseURL: `http://127.0.0.1:${frontendPort}`, httpCredentials: { username: 'fixture-user', password: 'fixture-application-password-never-real' }, trace: 'retain-on-failure' },
  projects: [{ name: 'desktop', use: { ...devices['Desktop Chrome'] } }, { name: 'mobile', use: { ...devices['Pixel 7'] } }],
  webServer: [
    { command: `../backend/.venv/bin/python -m uvicorn --app-dir .. backend.tests.fixtures.llm_http_server:app --host 127.0.0.1 --port ${providerPort}`, url: `http://127.0.0.1:${providerPort}/fixture/state`, reuseExistingServer: false },
    {
      command: `../backend/.venv/bin/python -m uvicorn --app-dir ../backend/src noris_ai.main:app --host 127.0.0.1 --port ${backendPort}`,
      url: `http://127.0.0.1:${backendPort}/api/v1/health/live`, reuseExistingServer: false,
      env: {
        NORIS_ENVIRONMENT: 'test', NORIS_LLM_PROVIDER: 'openai-compatible', NORIS_LLM_BASE_URL: `http://127.0.0.1:${providerPort}/v1`, NORIS_LLM_ALLOWED_HOSTS: '["127.0.0.1"]', NORIS_LLM_API_KEY: 'fixture-provider-key-never-real',
        NORIS_LLM_ACCESS_USERNAME: 'fixture-user', NORIS_LLM_ACCESS_PASSWORD: 'fixture-application-password-never-real', NORIS_LLM_ALLOWED_ORIGINS: JSON.stringify([`http://127.0.0.1:${frontendPort}`]),
        NORIS_LLM_MODELS: JSON.stringify(['fixture-alpha', 'fixture-beta', 'fixture-long'].map((id, index) => ({ id, name: ['Fixture Alpha', 'Fixture Beta', 'Fixture Long'][index], category: 'CHAT', token_limit_parameter: 'max_tokens', sources: ['fixture:local'], evidence: { category: 'VERIFIED', streaming: 'VERIFIED', token_limit_parameter: 'VERIFIED' }, ...(id !== 'fixture-beta' ? { context_window: 131072, provider_context_window: 131072, provider_limit_evidence: 'Local simulator only' } : {}), ...(id === 'fixture-long' ? { max_output_tokens: 32768, provider_max_output_tokens: 32768 } : {}) }))), NORIS_LLM_DEFAULT_MODEL: 'fixture-alpha',
        NORIS_LLM_CATALOG_TTL_SECONDS: '1', NORIS_LLM_DISCOVERY_RETRY_AFTER_SECONDS: '1', NORIS_LLM_MAX_OUTPUT_TOKENS: '32768',
        NORIS_LLM_REQUESTS_PER_MINUTE: '120', NORIS_LLM_TITLE_TIMEOUT_SECONDS: '2',
        NORIS_LLM_MAX_CONCURRENT: '4', NORIS_LLM_DAILY_TOKEN_BUDGET: '10000000', NORIS_LLM_TITLE_MAX_OUTPUT_TOKENS: '96',
        NORIS_LLM_READ_TIMEOUT_SECONDS: '30', NORIS_LLM_TOTAL_TIMEOUT_SECONDS: '120', NORIS_LLM_TOKEN_LIMIT_PARAMETER: 'max_tokens',
      },
    },
    {
      // Validate the shipped client, including reload and streaming cancellation.
      command: 'node node_modules/nuxt/bin/nuxt.mjs build && node ../scripts/serve-browser-fixture.mjs',
      url: `http://127.0.0.1:${frontendPort}`, reuseExistingServer: false, timeout: 180_000,
      env: { NORIS_E2E_BACKEND_PORT: String(backendPort), NORIS_E2E_FRONTEND_PORT: String(frontendPort), NUXT_PUBLIC_CHAT_TRANSPORT: 'real', NUXT_TELEMETRY_DISABLED: '1', NORIS_NUXT_BUILD_DIR: '.nuxt-llm' },
    },
  ],
})
