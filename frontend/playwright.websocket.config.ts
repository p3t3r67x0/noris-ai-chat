import { defineConfig, devices } from '@playwright/test'
import llm from './playwright.llm.config'

if (!process.env.NORIS_DATABASE_URL && !process.env.NORIS_E2E_COMPOSE_URL) throw new Error('Set NORIS_DATABASE_URL to a migrated disposable browser database')
const servers = Array.isArray(llm.webServer) ? llm.webServer : llm.webServer ? [llm.webServer] : []
export default defineConfig({
  ...llm,
  testDir: './tests/websocket', outputDir: './test-results/websocket',
  use: { ...llm.use, ...(process.env.NORIS_E2E_COMPOSE_URL ? { baseURL: process.env.NORIS_E2E_COMPOSE_URL } : {}), trace: 'retain-on-failure' },
  projects: [{ name: 'desktop', use: { ...devices['Desktop Chrome'] } }, { name: 'mobile', use: { ...devices['Pixel 7'] } }],
  webServer: process.env.NORIS_E2E_COMPOSE_URL ? [] : servers.map(server => {
    if (server.command.includes('noris_ai.main')) return { ...server, env: { ...server.env, NORIS_DATABASE_URL: process.env.NORIS_DATABASE_URL!, NORIS_MIGRATION_DATABASE_URL: process.env.NORIS_DATABASE_URL!, NORIS_CHAT_WS_ALLOWED_HOSTS: '["127.0.0.1:8592"]' } }
    if (server.command.includes('nuxt.mjs')) return { ...server, env: { ...server.env, NUXT_PUBLIC_CHAT_TRANSPORT: 'websocket', NUXT_PUBLIC_CHAT_WEBSOCKET_URL: 'ws://127.0.0.1:8592/api/v1/chat/ws' } }
    return server
  }),
})
