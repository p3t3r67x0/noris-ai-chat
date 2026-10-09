import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/live', workers: 1, retries: 0,
  use: {
    baseURL: process.env.NORIS_LIVE_APP_ORIGIN,
    httpCredentials: { username: process.env.NORIS_LLM_ACCESS_USERNAME ?? '', password: process.env.NORIS_LLM_ACCESS_PASSWORD ?? '' },
    trace: 'off', screenshot: 'off', video: 'off',
  },
})
