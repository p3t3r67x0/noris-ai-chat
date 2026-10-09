import { defineConfig } from '@playwright/test'
import base from './playwright.config'

// Run the same UI assertions and goldens against the already-started Compose
// production stack. Caddy keeps frontend, API and PostgreSQL on the same origin.
export default defineConfig({
  ...base,
  outputDir: './test-results/production',
  reporter: process.env.CI ? [['list'], ['html', { outputFolder: 'playwright-report/production', open: 'never' }]] : 'list',
  use: { ...base.use, baseURL: 'http://127.0.0.1:8080' },
  webServer: [],
})
