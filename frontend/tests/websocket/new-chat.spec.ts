import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { readFileSync } from 'node:fs'

const provider = `http://127.0.0.1:${process.env.NORIS_E2E_PROVIDER_PORT ?? 8591}`
const image = { name: 'synthetic.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAGUlEQVR4nGMMLJ7CQApgIkn1qIZRDUNKAwBO2QF44IsoTQAAAABJRU5ErkJggg==', 'base64') }
// Generated once with backend/tests/fixtures/attachments.py; browser runners need no Python.
const pdf = { name: 'synthetic.pdf', mimeType: 'application/pdf', buffer: readFileSync(new URL('../fixtures/synthetic.pdf', import.meta.url)) }

async function list(request: APIRequestContext) {
  return (await (await request.get('/api/v1/conversations', { params: { archived: true, limit: 100 } })).json()).conversations as { id: string, title: string, titleSource: string, sidebarVisible: boolean }[]
}
async function upload(page: Page, file: typeof image): Promise<void> {
  await expect(page.locator('.composer-attachment')).toBeEnabled()
  await page.locator('.composer-attachment').click()
  const chooser = page.waitForEvent('filechooser')
  await page.getByRole('menuitem', { name: /^Fotos und Dateien hinzufügen/ }).click()
  await (await chooser).setFiles(file)
  await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(1)
}
test.beforeEach(async ({ request }) => {
  for (const c of await list(request)) await request.delete(`/api/v1/conversations/${c.id}`)
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null, modelId: null } })
  await request.put('/api/v1/chat/drafts/new', { data: { content: '' } })
  await request.post(`${provider}/fixture/catalog`, { data: { ids: ['fixture-alpha', 'fixture-beta', 'fixture-long'], imageIds: ['fixture-alpha'] } })
})
test.afterEach(async ({ request }) => {
  await request.post(`${provider}/fixture/catalog`, { data: { ids: ['fixture-alpha', 'fixture-beta', 'fixture-long'] } })
})

for (const viewport of [{ width: 1700, height: 900 }, { width: 1440, height: 900 }, { width: 768, height: 1024 }, { width: 390, height: 844 }]) {
  for (const theme of ['light', 'dark']) {
    test(`new chat lifecycle and screenshots ${viewport.width} ${theme}`, async ({ page, request }, info) => {
      test.skip(info.project.name !== 'desktop', 'Capture each viewport once; touch regression runs separately.')
      test.setTimeout(60_000)
      await page.setViewportSize(viewport)
      await page.addInitScript(value => localStorage.setItem('noris-ai-theme', value), theme)
      let release!: () => void
      const held = new Promise<void>(resolve => { release = resolve })
      let commandHeld = false
      let holdStream = true
      let firstDelta = false
      const buffered: (string | Buffer)[] = []
      let flush!: () => void
      await page.routeWebSocket('**/api/v1/chat/ws', client => {
        const server = client.connectToServer()
        client.onMessage(async message => {
          if (JSON.parse(String(message)).type === 'chat.generate' && !commandHeld) {
            commandHeld = true
            await held
          }
          server.send(message)
        })
        server.onMessage(message => {
          const event = JSON.parse(String(message))
          if (holdStream && firstDelta) buffered.push(message)
          else {
            client.send(message)
            if (event.type === 'chat.generation.delta') firstDelta = true
          }
        })
        flush = () => { holdStream = false; buffered.splice(0).forEach(message => client.send(message)) }
      })
      const directory = resolve('../docs/screenshots/new-chat/after')
      await mkdir(directory, { recursive: true })
      async function capture(state: string): Promise<void> {
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
        await expect(page.locator('.chat-composer')).toHaveCount(1)
        await page.evaluate(() => document.fonts.ready)
        const path = resolve(directory, `${viewport.width}-${theme}-${state}.png`)
        await page.screenshot({ path, animations: 'disabled', caret: 'hide' })
        await info.attach(state, { path, contentType: 'image/png' })
      }
      await page.goto('/')
      const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
      await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
      await expect(page.locator('.composer-attachment')).toBeEnabled()
      await page.keyboard.press('Control+Shift+O')
      await expect(input).toBeFocused()
      expect(await list(request)).toHaveLength(0)
      await expect(page.locator('.conversation-row')).toHaveCount(0)
      const welcome = (await page.locator('.empty-chat').boundingBox())!
      const composer = (await page.locator('.chat-composer').boundingBox())!
      expect(composer.y - (welcome.y + welcome.height)).toBeLessThan(3)
      expect(composer.y).toBeLessThan(viewport.height * 0.65)
      await input.evaluate(element => { element.dataset.instance = 'same-composer' })
      await capture('empty')
      await input.fill('Erkläre mir SearXNG.')
      await capture('draft')
      await input.press('Enter')
      await expect.poll(() => commandHeld).toBe(true)
      await expect(page.locator('.empty-chat')).toHaveCount(0)
      await expect(input).toBeFocused()
      await expect(input).toHaveAttribute('data-instance', 'same-composer')
      await input.press('Enter')
      expect(await list(request)).toHaveLength(1)
      expect((await list(request))[0]?.sidebarVisible).toBe(false)
      await expect(page.locator('.conversation-row')).toHaveCount(0)
      await capture('sending')
      release()
      await expect(page.locator('[data-generation-status="streaming"]')).toBeAttached()
      await expect(page.locator('.message-assistant')).toContainText('Echte')
      await capture('streaming')
      flush()
      await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
      await capture('completed')
      await expect.poll(async () => (await list(request))[0]?.titleSource).toBe('generated')
      const conversation = (await list(request))[0]!
      expect(conversation.title).toBe('SearXNG Funktionsweise')
      const toggle = page.locator('.chat-header button[aria-controls="chat-sidebar"]')
      if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
      const row = page.locator(`.conversation-row[data-conversation-id="${conversation.id}"]`).filter({ visible: true })
      await expect(row.locator('button').first()).toHaveAttribute('title', conversation.title)
      await capture('sidebar-title')
      if (viewport.width < 1024) await page.getByRole('button', { name: 'Gesprächsliste schließen', exact: true }).click()
      await input.fill('Ein weiterer Entwurf')
      await expect(input).toHaveAttribute('data-instance', 'same-composer')
      const bottom = (await page.locator('.chat-composer').boundingBox())!
      expect(bottom.y + bottom.height).toBeGreaterThan(viewport.height - 45)
      await capture('active')
      await page.keyboard.press('Control+Shift+O')
      await input.fill('Entwurf mit Anhang')
      await upload(page, image)
      expect(await list(request)).toHaveLength(2)
      expect((await list(request)).filter(c => c.sidebarVisible)).toHaveLength(1)
      await expect(input).toHaveValue('Entwurf mit Anhang')
      await expect(input).toBeFocused()
      await capture('image')
      await page.getByRole('button', { name: 'synthetic.png entfernen' }).click()
      await upload(page, pdf)
      await capture('pdf')
      const prepared = (await list(request)).find(c => !c.sidebarVisible)!
      await expect.poll(async () => (await (await request.get('/api/v1/chat/drafts')).json()).drafts.find((d: { key: string }) => d.key === prepared.id)?.content).toBe('Entwurf mit Anhang')
      await page.reload()
      await expect(input).toHaveValue('Entwurf mit Anhang')
      await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(1)
      expect(await list(request)).toHaveLength(2)
      await expect(page.locator('.empty-chat')).toBeVisible()
      if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
      await page.locator(`.conversation-row[data-conversation-id="${conversation.id}"]`).filter({ visible: true }).locator('button').first().click()
      await expect(input).toHaveValue('Ein weiterer Entwurf')
      await page.keyboard.press('Control+Shift+O')
      await expect(input).toHaveValue('Entwurf mit Anhang')
      await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(1)
      expect(await list(request)).toHaveLength(2)
    })
  }
}

test('draft reload, first response failure, retry and title failure remain recoverable', async ({ page, request }, info) => {
  await page.goto('/')
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await expect(page.locator('.composer-attachment')).toBeEnabled()
  await input.fill('Noch ungesendeter Entwurf')
  await expect.poll(async () => (await (await request.get('/api/v1/chat/drafts')).json()).drafts.find((d: { key: string }) => d.key === '__new__')?.content).toBe('Noch ungesendeter Entwurf')
  await page.reload()
  await expect(input).toHaveValue('Noch ungesendeter Entwurf')
  expect(await list(request)).toHaveLength(0)
  await input.fill(`/retry new-chat ${info.project.name} ${crypto.randomUUID()}`)
  await input.press('Enter')
  await expect(page.locator('[data-generation-status="failed"]')).toBeAttached()
  const failed = (await list(request))[0]!
  expect(failed.sidebarVisible).toBe(true)
  expect(failed.title).not.toBe('Neuer Chat')
  await page.reload()
  await expect(page.locator('.message-user')).toContainText('/retry new-chat')
  await page.locator('.message-assistant').getByRole('button', { name: 'Erneut versuchen', exact: true }).click()
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  expect(await list(request)).toHaveLength(1)
  async function titleErrorCalls(): Promise<number> {
    const state = await (await request.get(`${provider}/fixture/state`)).json()
    return state.title_calls.filter((call: { messages: { content: string }[] }) => call.messages.at(-1)?.content === '/title-error SearXNG').length
  }
  const previousTitleErrors = await titleErrorCalls()
  await page.keyboard.press('Control+Shift+O')
  await input.fill('/title-error SearXNG')
  await input.press('Enter')
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  // The retry's asynchronous title can reorder the list after this chat completes.
  const conversations = await list(request)
  expect(conversations).toHaveLength(2)
  const conversation = conversations.find(c => c.id !== failed.id)!
  await expect.poll(titleErrorCalls).toBe(previousTitleErrors + 1)
  expect(conversation.sidebarVisible).toBe(true)
  expect(conversation.titleSource).toBe('fallback')
  expect(conversation.title).not.toBe('Neuer Chat')
  await page.reload()
  await expect(page.locator('.message-user')).toContainText('/title-error SearXNG')
  expect((await (await request.get(`/api/v1/conversations/${conversation.id}`)).json()).titleSource).toBe('fallback')
  expect(await titleErrorCalls()).toBe(previousTitleErrors + 1)
})

test('visualViewport keyboard and landscape keep the empty composer and heading visible', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await expect(page.locator('.composer-attachment')).toBeEnabled()
  await input.fill('Erste Zeile\nZweite Zeile\nDritte Zeile')
  await page.evaluate(() => {
    Object.defineProperty(window.visualViewport, 'height', { configurable: true, value: 360 })
    Object.defineProperty(window.visualViewport, 'offsetTop', { configurable: true, value: 20 })
    window.visualViewport?.dispatchEvent(new Event('resize'))
  })
  await expect.poll(() => page.locator('.chat-workspace').evaluate(element => element.getBoundingClientRect().height)).toBe(360)
  const composer = (await page.locator('.chat-composer').boundingBox())!
  expect(composer.y + composer.height).toBeLessThanOrEqual(380)
  await expect(page.locator('.empty-chat')).toBeVisible()
  await input.focus()
  await page.setViewportSize({ width: 844, height: 390 })
  await expect(input).toBeFocused()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
