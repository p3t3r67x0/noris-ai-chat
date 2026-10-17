// Synthetic, loopback-only browser evidence. Run against the mock transport.
import { chromium, expect } from '../frontend/node_modules/@playwright/test/index.mjs'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const stage = process.argv[2]
if (stage !== 'before' && stage !== 'after') throw new Error('Usage: node scripts/capture-chat-shell.mjs before|after')
const origin = new URL(process.env.NORIS_SHELL_URL ?? 'http://127.0.0.1:3000')
if (!['127.0.0.1', 'localhost', '[::1]'].includes(origin.hostname)) throw new Error('Use a local synthetic browser fixture')
const root = fileURLToPath(new URL('../docs/ui-reference/october-2026/', import.meta.url))
await mkdir(root, { recursive: true })
const selectors = ['.chat-rail', '.conversation-sidebar', '.sidebar-heading', '.sidebar-new-chat', '.sidebar-section', '.conversation-row', '.chat-composer', '.composer-input', '.composer-attachment', '.composer-model', '.composer-microphone', '.composer-submit', '.empty-chat h1']
const browser = await chromium.launch()
try {
  for (const theme of ['light', 'dark']) for (const [width, height] of [[1701, 863], [1440, 900], [1280, 800], [1024, 768], [768, 1024], [390, 844]]) {
    const context = await browser.newContext({ viewport: { width, height }, locale: 'de-DE', deviceScaleFactor: 1, colorScheme: theme })
    try {
      const page = await context.newPage()
      await page.addInitScript(theme => localStorage.setItem('noris-ai-theme', theme), theme)
      await page.goto(origin.href)
      await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      // Mobile hides the label, but its presence is specific to mock mode.
      await expect(page.locator('.header-demo')).toHaveCount(1)
      await expect(page.locator('.chat-composer')).toHaveCount(1)
      await page.evaluate(() => document.fonts.ready)
      await page.screenshot({ path: `${root}/${stage}-${width}-${theme}.png`, animations: 'disabled', caret: 'hide' })
      const metrics = await page.evaluate(selectors => Object.fromEntries(selectors.map(selector => [selector, document.querySelector(selector)?.getBoundingClientRect().toJSON() ?? null])), selectors)
      await writeFile(`${root}/${stage}-${width}-${theme}.json`, JSON.stringify(metrics, null, 2) + '\n')
    }
    finally { await context.close() }
  }
}
finally { await browser.close() }
