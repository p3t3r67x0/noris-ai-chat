import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests/notifications', outputDir: './test-results/notifications',
  fullyParallel: false, workers: 1, retries: 0, reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:8792', locale: 'de-DE', trace: 'retain-on-failure' },
  webServer: {
    command: 'node .output/server/index.mjs', url: 'http://127.0.0.1:8792', reuseExistingServer: false,
    env: { PORT: '8792', HOST: '127.0.0.1', NUXT_PUBLIC_CHAT_TRANSPORT: 'websocket' },
  },
})
