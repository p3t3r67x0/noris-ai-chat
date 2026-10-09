import { defineConfig } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const enabled = process.env.NORIS_RUN_LIVE_LLM_SMOKE === '1'
const session = enabled ? process.env.NORIS_LIVE_SESSION : undefined
const credentials: unknown = !enabled ? { username: '', password: '' } : session ? JSON.parse(readFileSync(join(session, 'access.json'), 'utf8')) : {
  username: process.env.NORIS_LLM_ACCESS_USERNAME ?? '', password: process.env.NORIS_LLM_ACCESS_PASSWORD ?? '',
}
if (!credentials || typeof credentials !== 'object' || !('username' in credentials) || typeof credentials.username !== 'string' || !('password' in credentials) || typeof credentials.password !== 'string') throw new Error('Application access credentials are missing.')

export default defineConfig({
  testDir: './tests/live', workers: 1, retries: 0,
  outputDir: './test-results/live',
  preserveOutput: 'never',
  use: {
    baseURL: process.env.NORIS_LIVE_APP_ORIGIN,
    httpCredentials: { username: credentials.username, password: credentials.password },
    trace: 'off', screenshot: 'off', video: 'off',
  },
})
