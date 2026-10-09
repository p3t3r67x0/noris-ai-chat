import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/llm',
  outputDir: './test-results/llm',
  workers: 1, retries: 0,
  use: { baseURL: 'http://127.0.0.1:8593', httpCredentials: { username: 'fixture-user', password: 'fixture-application-password-never-real' }, trace: 'retain-on-failure' },
  projects: [{ name: 'desktop', use: { ...devices['Desktop Chrome'] } }, { name: 'mobile', use: { ...devices['Pixel 7'] } }],
  webServer: [
    { command: '../backend/.venv/bin/python -m uvicorn --app-dir .. backend.tests.fixtures.llm_http_server:app --host 127.0.0.1 --port 8591', url: 'http://127.0.0.1:8591/fixture/state', reuseExistingServer: false },
    {
      command: '../backend/.venv/bin/python -m uvicorn --app-dir ../backend/src noris_ai.main:app --host 127.0.0.1 --port 8592',
      url: 'http://127.0.0.1:8592/api/v1/health/live', reuseExistingServer: false,
      env: {
        NORIS_ENVIRONMENT: 'test', NORIS_LLM_PROVIDER: 'openai-compatible', NORIS_LLM_BASE_URL: 'http://127.0.0.1:8591/v1', NORIS_LLM_ALLOWED_HOSTS: '["127.0.0.1"]', NORIS_LLM_API_KEY: 'fixture-provider-key-never-real',
        NORIS_LLM_ACCESS_USERNAME: 'fixture-user', NORIS_LLM_ACCESS_PASSWORD: 'fixture-application-password-never-real', NORIS_LLM_ALLOWED_ORIGINS: '["http://127.0.0.1:8593"]',
        NORIS_LLM_MODELS: JSON.stringify(['fixture-alpha', 'fixture-beta', 'fixture-long'].map((id, index) => ({ id, name: ['Fixture Alpha', 'Fixture Beta', 'Fixture Long'][index], category: 'CHAT', token_limit_parameter: 'max_tokens', sources: ['fixture:local'], evidence: { category: 'VERIFIED', streaming: 'VERIFIED', token_limit_parameter: 'VERIFIED' }, ...(id === 'fixture-long' ? { context_window: 131072, max_output_tokens: 32768, provider_max_output_tokens: 32768, provider_limit_evidence: 'Local simulator only' } : {}) }))), NORIS_LLM_DEFAULT_MODEL: 'fixture-alpha',
        NORIS_LLM_CATALOG_TTL_SECONDS: '1', NORIS_LLM_DISCOVERY_RETRY_AFTER_SECONDS: '1', NORIS_LLM_REQUESTS_PER_MINUTE: '120', NORIS_LLM_TITLE_TIMEOUT_SECONDS: '2',
        NORIS_LLM_MAX_CONCURRENT: '4', NORIS_LLM_DAILY_TOKEN_BUDGET: '2000000', NORIS_LLM_MAX_OUTPUT_TOKENS: '32768', NORIS_LLM_TITLE_MAX_OUTPUT_TOKENS: '96',
        NORIS_LLM_READ_TIMEOUT_SECONDS: '30', NORIS_LLM_TOTAL_TIMEOUT_SECONDS: '120', NORIS_LLM_TOKEN_LIMIT_PARAMETER: 'max_tokens',
      },
    },
    { command: 'node node_modules/nuxt/bin/nuxt.mjs dev --host 127.0.0.1 --port 8593', url: 'http://127.0.0.1:8593', reuseExistingServer: false, timeout: 60_000, env: { NORIS_DEV_API_TARGET: 'http://127.0.0.1:8592', NUXT_PUBLIC_CHAT_TRANSPORT: 'real', NUXT_TELEMETRY_DISABLED: '1' } },
  ],
})
