import { clearTestConversations, stableModelCatalog } from './chat-fixtures'
import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import type { ApiSchemas } from '../../app/types/generated/api'

const provider = `http://127.0.0.1:${process.env.NORIS_E2E_PROVIDER_PORT ?? 8591}`
type Conversation = ApiSchemas['ConversationResponse']
async function list(request: APIRequestContext, params: Record<string, string> = {}): Promise<Conversation[]> {
  return (await (await request.get('/api/v1/conversations', { params: { limit: '100', ...params } })).json()).conversations
}
async function openSearch(page: Page) {
  await page.keyboard.press('Control+k')
  const dialog = page.getByRole('dialog', { name: 'Chats suchen', exact: true })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('combobox')).toBeFocused()
  return dialog
}
async function newChat(page: Page) {
  const toggle = page.locator('.rail-sidebar-open:visible, .chat-header button[aria-controls="chat-sidebar"][aria-expanded="false"]:visible, .sidebar-heading button[aria-controls="chat-sidebar"][aria-expanded="true"]:visible')
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  await page.locator('.sidebar-primary-actions').filter({ visible: true }).getByRole('button', { name: 'Neuer Chat', exact: true }).click()
  // Mobile focus remains trapped until the drawer's closing transition ends.
  await expect(page.locator('[role="dialog"]').filter({ has: page.locator('.sidebar-primary-actions') })).toHaveCount(0)
  await expect(page.getByRole('textbox', { name: 'Nachricht', exact: true })).toBeFocused()
}
test.beforeEach(async ({ page, request }) => {
  await stableModelCatalog(page)
  await clearTestConversations(request)
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null, modelId: 'fixture-alpha' } })
  await request.put('/api/v1/chat/drafts/new', { data: { content: '' } })
  await request.post(`${provider}/fixture/catalog`, { data: { ids: ['fixture-alpha', 'fixture-beta', 'fixture-long'], imageIds: ['fixture-alpha'] } })
  await expect.poll(async () => {
    const catalog = await (await request.get('/api/v1/llm/models')).json()
    return catalog.models.find((model: { id: string, vision?: boolean }) => model.id === 'fixture-alpha')?.vision
  }).toBe(true)
  // This suite checks conversation visibility and attachment recovery. Keep
  // the verified catalog stable so its one-second fixture TTL cannot disable
  // Send between key-down and key-up; refresh has separate regression coverage.
  await page.route('**/api/v1/llm/models', async (route) => {
    const response = await route.fetch()
    await route.fulfill({ response, json: { ...await response.json(), expires_in_seconds: 60 } })
  })
})
test.afterEach(async ({ request }) => {
  await request.post(`${provider}/fixture/catalog`, { data: { ids: ['fixture-alpha', 'fixture-beta', 'fixture-long'] } })
})

test('new chat stays hidden; first persisted input and titles update an open search in both tabs', async ({ page, context, request }, info) => {
  const second = await context.newPage()
  const connected = new Set<Page>()
  for (const tab of [page, second]) tab.on('websocket', socket => socket.on('framereceived', frame => {
    if (JSON.parse(String(frame.payload)).type === 'chat.connected') connected.add(tab)
  }))
  await Promise.all([page.goto('/'), second.goto('/')])
  for (const tab of [page, second]) await expect(tab.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  // Mounted UI is earlier than authenticated metadata delivery. Both real
  // sockets must be ready before testing a live cross-tab broadcast.
  await expect.poll(() => connected.size).toBe(2)
  await newChat(page)
  const dialog = await openSearch(page)
  await expect(dialog.getByRole('option')).toHaveCount(0)
  await page.screenshot({ path: info.outputPath('empty-search.png') })
  await page.keyboard.press('Escape')
  // A historical technical row is also excluded, even with the old visible flag.
  const legacy = await request.post('/api/v1/conversations', { data: {} })
  expect(legacy.ok()).toBe(true)
  const remote = await openSearch(second)
  await expect(remote.getByRole('option')).toHaveCount(0)
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).fill('/title-summary-switch')
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).press('Enter')
  await expect.poll(async () => (await list(request)).length).toBe(1)
  await expect(remote.getByRole('option')).toHaveCount(1)
  await expect.poll(async () => (await list(request))[0]?.titleSource).toBe('generated')
  const saved = (await list(request))[0]!
  expect(saved.title).toBe('Automatische Chat-Zusammenfassungen')
  await expect(remote.getByRole('option')).toContainText(saved.title)
  const local = await openSearch(page)
  await expect(local.getByRole('option')).toContainText(saved.title)
  await page.screenshot({ path: info.outputPath('started-search.png') })
  for (const tab of [page, second]) {
    await tab.keyboard.press('Escape')
    await tab.reload()
    await expect(tab.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    await expect((await openSearch(tab)).getByRole('option')).toContainText(saved.title)
  }
  await remote.getByRole('combobox').fill('Neuer Chat')
  await expect(remote.getByRole('option')).toHaveCount(0)
  const renamed = await request.patch(`/api/v1/conversations/${saved.id}`, { data: { title: 'Neuer Chat', version: saved.version } })
  expect(renamed.ok()).toBe(true)
  // A real conversation remains findable under a manually chosen fallback name.
  await expect(remote.getByRole('option')).toHaveText('Neuer Chat')
  await expect(local.getByRole('option')).toHaveText('Neuer Chat')
  const manual: Conversation = await renamed.json()
  expect((await request.patch(`/api/v1/conversations/${saved.id}`, { data: { archived: true, version: manual.version } })).ok()).toBe(true)
  await expect(remote.getByRole('option')).toHaveCount(0)
  await expect(local.getByRole('option')).toHaveCount(0)
  expect((await list(request, { archiveOnly: 'true' })).map(row => row.id)).toEqual([saved.id])
  await second.close()
})

const files = [
  { name: 'synthetic.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAGUlEQVR4nGMMLJ7CQApgIkn1qIZRDUNKAwBO2QF44IsoTQAAAABJRU5ErkJggg==', 'base64') },
  { name: 'synthetic.pdf', mimeType: 'application/pdf', buffer: readFileSync(new URL('../fixtures/synthetic.pdf', import.meta.url)) },
]
for (const file of files) {
  test(`${file.name}: upload and draft remain recoverable but absent from all search lists`, async ({ page, request }) => {
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    await newChat(page)
    const composer = page.getByRole('textbox', { name: 'Nachricht', exact: true })
    await composer.fill('Unsent attachment draft')
    await page.locator('.composer-attachment').click()
    const chooser = page.waitForEvent('filechooser')
    await page.getByRole('menuitem', { name: /^Fotos und Dateien hinzufügen/ }).click()
    await (await chooser).setFiles(file)
    await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(1)
    expect(await list(request)).toEqual([])
    const [prepared] = await list(request, { preparedOnly: 'true' })
    expect(prepared?.lifecycle).toBe('EMPTY')
    await expect.poll(async () => (await (await request.get('/api/v1/chat/drafts')).json()).drafts.find((d: { key: string }) => d.key === prepared!.id)?.content).toBe('Unsent attachment draft')
    const dialog = await openSearch(page)
    await expect(dialog.getByRole('option')).toHaveCount(0)
    await dialog.getByRole('combobox').fill('Neuer Chat')
    await expect(dialog.getByRole('option')).toHaveCount(0)
    // Recover even after leaving the preparation before reloading.
    await page.keyboard.press('Escape')
    await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null } })
    await page.reload()
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    await newChat(page)
    await expect(composer).toHaveValue('Unsent attachment draft')
    await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(1)
    expect(await list(request)).toEqual([])
    await composer.fill('/slow')
    await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
    await composer.press('Enter')
    await expect(page.locator('[data-generation-status="streaming"]')).toBeAttached()
    await page.getByRole('button', { name: 'Antwort stoppen', exact: true }).click()
    await expect(page.locator('[data-generation-status="cancelled"]')).toBeAttached()
    expect((await list(request)).map(row => row.id)).toEqual([prepared!.id])
    await expect((await openSearch(page)).getByRole('option')).toHaveCount(1)
  })
}
