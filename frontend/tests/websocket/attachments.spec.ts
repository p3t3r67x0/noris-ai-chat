import { expectSelectedModel, selectChatModel } from '../e2e/model-helpers'
import { clearTestConversations, stableModelCatalog } from './chat-fixtures'
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

const fixtureOrigin = `http://127.0.0.1:${Number(process.env.NORIS_E2E_PROVIDER_PORT ?? 8591)}`
const fixtureModels = ['fixture-alpha', 'fixture-beta', 'fixture-long']
test.beforeEach(async ({ request }) => {
  await request.post(`${fixtureOrigin}/fixture/catalog`, { data: { ids: fixtureModels } })
  await clearTestConversations(request)
  await request.put('/api/v1/chat/drafts/new', { data: { content: '' } })
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null, modelId: null } })
})
test.afterEach(async ({ request }) => {
  await request.post(`${fixtureOrigin}/fixture/catalog`, { data: { ids: fixtureModels } })
})

const textFile = { name: 'synthetic.txt', mimeType: 'text/plain', buffer: Buffer.from('Synthetic upload context for the local simulator.') }
async function selectFiles(page: Page, files = [textFile]): Promise<void> {
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await expect(page.locator('.composer-attachment')).toBeEnabled()
  await page.locator('.composer-attachment').click()
  const chooser = page.waitForEvent('filechooser')
  await page.getByRole('menuitem', { name: /^Fotos und Dateien hinzufügen/ }).click()
  await (await chooser).setFiles(files)
}

test('native multiple selection persists previews, layout and server context through reload', async ({ page, request }) => {
  await page.goto('/')
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await expect(page.locator('.composer-container')).toHaveAttribute('data-layout', 'compact')
  const original = (await page.locator('.chat-composer').boundingBox())!
  await selectFiles(page, [textFile, { name: 'synthetic.md', mimeType: 'text/markdown', buffer: Buffer.from('# Synthetic markdown\nA second attachment.') }])
  await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(2)
  await expect(page.locator('.composer-container')).toHaveAttribute('data-layout', 'expanded')
  await expect(input).toBeFocused()
  const attached = (await page.locator('.chat-composer').boundingBox())!
  // A new draft grows with its welcome/composer group; active chats stay docked.
  expect(attached.height).toBeGreaterThan(original.height)
  expect(attached.y + attached.height).toBeLessThan(page.viewportSize()!.height)
  await input.fill('Summarize the synthetic attachments')
  await page.reload()
  await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(2)
  await expect(input).toHaveValue('Summarize the synthetic attachments')
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
  await input.press('Enter')
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  await expect(page.locator('.message-attachments a')).toHaveCount(2)
  const conversation = (await (await request.get('/api/v1/conversations')).json()).conversations[0]
  const messages = (await (await request.get(`/api/v1/conversations/${conversation.id}/messages`)).json()).messages
  expect(messages[0].content).toBe('Summarize the synthetic attachments')
  expect(messages[0].attachments).toHaveLength(2)
  const attachment = messages[0].attachments.find((file: { originalFilename: string }) => file.originalFilename === textFile.name)
  expect(attachment).toBeDefined()
  const download = await request.get(`/api/v1/chat/attachments/${attachment.id}/content`)
  expect(download.ok()).toBe(true)
  expect((await download.body()).toString()).toBe(textFile.buffer.toString())
  await page.reload()
  await expect(page.locator('.message-attachments a')).toHaveCount(2)
  await expect(page.locator('.attachment-preview')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('upload error retries the real API and removing the last file restores compact mode', async ({ page }) => {
  let failed = false
  await page.route('**/api/v1/chat/attachments?*', async route => {
    if (route.request().method() === 'POST' && !failed) {
      failed = true
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'INTERNAL_ERROR', message: 'Synthetischer Uploadfehler' } }) })
    }
    else await route.continue()
  })
  await page.goto('/')
  await selectFiles(page)
  await expect(page.locator('[data-upload-status="failed"]')).toContainText('Der Chatdienst konnte die Anfrage gerade nicht bearbeiten.')
  await expect(page.locator('[data-upload-status="failed"]')).not.toContainText('Synthetischer Uploadfehler')
  await page.getByRole('button', { name: 'synthetic.txt erneut hochladen' }).click()
  await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(1)
  await page.getByRole('button', { name: 'synthetic.txt entfernen' }).click()
  await expect(page.locator('.attachment-preview')).toHaveCount(0)
  await expect(page.getByRole('textbox', { name: 'Nachricht', exact: true })).toBeFocused()
  await expect(page.locator('.composer-container')).toHaveAttribute('data-layout', 'compact')
  await page.reload()
  await expect(page.locator('.attachment-preview')).toHaveCount(0)
})

test('removing an in-flight upload aborts its request without leaving a preview', async ({ page }) => {
  let release!: () => void
  const held = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/v1/chat/attachments?*', async route => {
    if (route.request().method() === 'POST') { await held; await route.abort() }
    else await route.continue()
  })
  await page.goto('/')
  await selectFiles(page)
  await expect(page.locator('[data-upload-status="uploading"]')).toHaveCount(1)
  await page.getByRole('button', { name: 'synthetic.txt entfernen' }).click()
  release()
  await expect(page.locator('.attachment-preview')).toHaveCount(0)
  await expect(page.getByRole('textbox', { name: 'Nachricht', exact: true })).toBeFocused()
  await expect(page.locator('.composer-container')).toHaveAttribute('data-layout', 'compact')
})

test('file count, type and size limits are visible and never create usable attachments', async ({ page, request }) => {
  await page.goto('/')
  await selectFiles(page, Array.from({ length: 6 }, (_, i) => ({ ...textFile, name: `synthetic-${i}.txt` })))
  await expect(page.locator('.composer-dock').getByRole('alert')).toContainText('Maximal 5 Dateien')
  await expect(page.locator('.attachment-preview')).toHaveCount(0)
  const conversations = await request.get('/api/v1/conversations')
  expect(conversations.ok()).toBe(true)
  expect((await conversations.json()).conversations).toHaveLength(0)
  await selectFiles(page, [{ name: 'synthetic.zip', mimeType: 'application/zip', buffer: Buffer.from('Synthetic invalid archive') }])
  await expect(page.locator('[data-upload-status="failed"]')).toContainText('Dateityp wird nicht unterstützt')
  await page.getByRole('button', { name: 'synthetic.zip entfernen' }).click()
  await selectFiles(page, [{ ...textFile, buffer: Buffer.alloc(10_485_761, 'x') }])
  await expect(page.locator('[data-upload-status="failed"]')).toContainText('Die Datei ist leer oder zu groß.')
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeDisabled()
})

for (const width of [1920, 1701, 1440, 390]) {
  for (const theme of ['light', 'dark']) {
    test(`confirmed attachment preview ${width} ${theme}`, async ({ page }, info) => {
      test.skip(info.project.name !== 'desktop', 'The screenshot matrix runs once; upload interactions also run with touch emulation.')
      await page.setViewportSize({ width, height: width === 1920 ? 976 : width === 1701 ? 863 : width === 390 ? 844 : 900 })
      await page.addInitScript(value => localStorage.setItem('noris-ai-theme', value), theme)
      await page.goto('/')
      await selectFiles(page)
      await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(1)
      await expect(page).toHaveScreenshot(`attachment-${width}-${theme}.png`, { animations: 'disabled', caret: 'hide' })
      await page.getByRole('textbox', { name: 'Nachricht', exact: true }).fill('Additional wrapped text for the synthetic attachment. '.repeat(10))
      await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(1)
      await selectChatModel(page, 'Fixture Beta')
      const positions = await page.locator('.composer-toolbar button').evaluateAll(elements => elements.map(e => { const r = e.getBoundingClientRect(); return r.y + r.height / 2 }))
      expect(new Set(positions).size).toBe(1)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      if (width === 390) {
        await page.evaluate(() => {
          Object.defineProperty(visualViewport!, 'height', { configurable: true, value: 250 })
          visualViewport!.dispatchEvent(new Event('resize'))
        })
        await expect.poll(() => page.locator('.chat-workspace').evaluate(element => element.getBoundingClientRect().height)).toBe(250)
        const box = (await page.locator('.chat-composer').boundingBox())!
        expect(box.y).toBeGreaterThanOrEqual(0)
        expect(box.y + box.height).toBeLessThanOrEqual(250)
        await expect(page.locator('.composer-submit')).toBeInViewport()
      }
    })
  }
}


const imageFile = { name: 'synthetic.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAGUlEQVR4nGMMLJ7CQApgIkn1qIZRDUNKAwBO2QF44IsoTQAAAABJRU5ErkJggg==', 'base64') }

test('a validated image requires explicit selection of a compatible model', async ({ page }) => {
  await page.goto('/')
  await selectFiles(page, [imageFile])
  await expect(page.locator('[data-upload-status="uploaded"]')).toContainText('Wähle ein Modell mit Bildeingabe')
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).fill('Describe this synthetic image')
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeDisabled()
  await page.reload()
  await expect(page.locator('[data-upload-status="uploaded"]')).toContainText('Wähle ein Modell mit Bildeingabe')
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeDisabled()
})

test('vision attachments survive model changes and reload and reach the provider as image parts', async ({ page, request }) => {
  // This case exercises model capabilities and the preserved image request.
  // Keep the fixture catalog valid across Enter; expiry has its own regressions.
  await request.post(`${fixtureOrigin}/fixture/catalog`, { data: { ids: fixtureModels, imageIds: ['fixture-beta'] } })
  // The backend can still cache the preceding text-only fixture for one second.
  // Verify the updated capability before retaining its metadata in the browser.
  await expect.poll(async () => {
    const catalog = await (await request.get('/api/v1/llm/models')).json()
    return catalog.models.find((model: { id: string, vision?: boolean }) => model.id === 'fixture-beta')?.vision
  }).toBe(true)
  await stableModelCatalog(page)
  await page.goto('/')
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.evaluate(element => { element.dataset.instance = 'original-vision-composer' })
  await selectFiles(page, [imageFile])
  await input.fill('Describe this synthetic image')
  await expect(page.locator('.composer-submit')).toBeDisabled()
  await selectChatModel(page, 'Fixture Beta')
  await expect(page.locator('[data-upload-status="uploaded"]')).toContainText('Für Bildanalyse bereit')
  await expect(input).toHaveAttribute('data-instance', 'original-vision-composer')
  await expect(page.locator('.composer-submit')).toBeEnabled()
  await selectChatModel(page, 'Fixture Alpha')
  await expect(page.locator('.composer-submit')).toBeDisabled()
  await expect(page.locator('.attachment-preview')).toHaveCount(1)
  await selectChatModel(page, 'Fixture Beta')
  await page.reload()
  await expect(page.locator('[data-upload-status="uploaded"]')).toContainText('Für Bildanalyse bereit')
  await expect(input).toHaveValue('Describe this synthetic image')
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
  await input.press('Enter')
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  await expect(page.locator('.message-attachments a')).toHaveCount(1)
  const state = await (await request.get(`${fixtureOrigin}/fixture/state`)).json()
  const call = state.calls.at(-1)
  expect(call.model).toBe('fixture-beta')
  expect(call.messages[0].content[0].type).toBe('text')
  expect(call.messages[0].content[1].image_url.url).toMatch(/^data:image\/jpeg;base64,/)
  const image = page.getByRole('img', { name: 'Angehängtes Bild: synthetic.png', exact: true })
  await expect(image).toBeVisible()
  await expect.poll(() => image.evaluate(element => (element as HTMLImageElement).naturalWidth)).toBe(16)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.reload()
  await expect(page.locator('.message-attachments a')).toHaveCount(1)
  await expect(image).toBeVisible()
  await expect.poll(() => image.evaluate(element => (element as HTMLImageElement).naturalWidth)).toBe(16)
})

test('a failed saved-image preview retries without changing the chat or model', async ({ page, request }) => {
  await request.post(`${fixtureOrigin}/fixture/catalog`, { data: { ids: fixtureModels, imageIds: ['fixture-beta'] } })
  await expect.poll(async () => {
    const catalog = await (await request.get('/api/v1/llm/models')).json()
    return catalog.models.find((model: { id: string, vision?: boolean }) => model.id === 'fixture-beta')?.vision
  }).toBe(true)
  // The fixture's one-second catalog expiry can disable Send between the
  // mouse actionability check and pointer dispatch. Keep this preview test's
  // verified catalog stable; catalog-refresh behavior has separate coverage.
  await page.route('**/api/v1/llm/models', async route => {
    const response = await route.fetch()
    const catalog = await response.json()
    await route.fulfill({ response, json: { ...catalog, expires_in_seconds: 60 } })
  })
  let failed = false
  await page.route('**/api/v1/chat/attachments/*/content?preview=true', async route => {
    if (!failed) {
      failed = true
      await route.fulfill({ status: 503, contentType: 'application/json', body: '{}' })
    }
    else await route.continue()
  })
  await page.goto('/')
  await selectFiles(page, [imageFile])
  await selectChatModel(page, 'Fixture Beta')
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.fill('Describe this synthetic image')
  await expect(page.locator('[data-upload-status="uploaded"]')).toContainText('Für Bildanalyse bereit')
  await page.getByRole('button', { name: 'Nachricht senden', exact: true }).click()
  await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
  await expect(page.locator('.message-image-error')).toContainText('Bildvorschau konnte nicht geladen werden')
  await expect(page.locator('.message-attachments a')).toHaveCount(1)
  const conversationId = (await (await request.get('/api/v1/conversations')).json()).conversations[0].id
  const before = (await (await request.get(`${fixtureOrigin}/fixture/state`)).json()).calls.length
  await page.getByRole('button', { name: 'synthetic.png: Bildvorschau erneut laden', exact: true }).click()
  const image = page.getByRole('img', { name: 'Angehängtes Bild: synthetic.png', exact: true })
  await expect.poll(() => image.evaluate(element => (element as HTMLImageElement).naturalWidth)).toBe(16)
  await expect(page.locator('.message-image-error')).toHaveCount(0)
  await expectSelectedModel(page, 'Fixture Beta')
  expect((await (await request.get('/api/v1/conversations')).json()).conversations[0].id).toBe(conversationId)
  expect((await (await request.get(`${fixtureOrigin}/fixture/state`)).json()).calls.length).toBe(before)
})

test('stopping a vision response preserves the composer and saved attachment', async ({ page, request }) => {
  await request.post(`${fixtureOrigin}/fixture/catalog`, { data: { ids: fixtureModels, imageIds: ['fixture-beta'] } })
  // Match the other vision cases: await changed metadata and keep it valid
  // across Enter so catalog expiry cannot swallow the cancellation setup.
  await expect.poll(async () => {
    const catalog = await (await request.get('/api/v1/llm/models')).json()
    return catalog.models.find((model: { id: string, vision?: boolean }) => model.id === 'fixture-beta')?.vision
  }).toBe(true)
  await stableModelCatalog(page)
  await page.goto('/')
  await selectFiles(page, [imageFile])
  await selectChatModel(page, 'Fixture Beta')
  const input = page.getByRole('textbox', { name: 'Nachricht', exact: true })
  await input.evaluate(element => { element.dataset.instance = 'vision-stop' })
  await input.fill('/slow Describe this synthetic image')
  await expect(page.locator('.composer-submit')).toBeEnabled()
  await input.press('Enter')
  await expect(page.locator('[data-generation-status="streaming"]')).toBeAttached()
  await page.getByRole('button', { name: 'Antwort stoppen', exact: true }).click()
  await expect(page.locator('[data-generation-status="cancelled"]')).toBeAttached()
  await expect(input).toBeFocused()
  await expect(input).toHaveAttribute('data-instance', 'vision-stop')
  await expect(page.locator('.message-attachments a')).toHaveCount(1)
})
