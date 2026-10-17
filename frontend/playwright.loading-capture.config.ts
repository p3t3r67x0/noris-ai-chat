import { defineConfig } from '@playwright/test'

if (!process.env.NORIS_LOADING_CAPTURE_URL) throw new Error('Set NORIS_LOADING_CAPTURE_URL to a local WebSocket-mode build')
export default defineConfig({
  testDir: './tests/loading-capture', outputDir: './test-results/loading-capture', workers: 1, retries: 0,
  use: { baseURL: process.env.NORIS_LOADING_CAPTURE_URL, viewport: { width: 1920, height: 976 }, deviceScaleFactor: 1, locale: 'de-DE', reducedMotion: 'reduce' },
})
