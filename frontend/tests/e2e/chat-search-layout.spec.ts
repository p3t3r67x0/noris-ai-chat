import { expect, test } from '@playwright/test'
import type { Locator } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import { savedChat, seedChat } from './chat-fixtures'

test.use({ deviceScaleFactor: 1 })
const phase = process.env.NORIS_UI_CAPTURE_PHASE ?? 'after'
const evidence = fileURLToPath(new URL(`../../../docs/chat-search/evidence/${phase}`, import.meta.url))

export async function searchGeometry(dialog: Locator) {
  return dialog.evaluate(element => {
    const rect = (node: Element | null) => node?.getBoundingClientRect().toJSON() ?? null
    return {
      dialog: rect(element), input: rect(element.querySelector('input')), inputWrapper: rect(element.querySelector('.chat-search-input')), categories: rect(element.querySelector('.chat-search-categories')),
      viewport: rect(element.querySelector('.chat-search-viewport')), footer: rect(element.querySelector('.chat-search-footer')),
      environment: { viewport: [innerWidth, innerHeight], dpr: devicePixelRatio, scale: visualViewport?.scale },
      rows: [...element.querySelectorAll('[role="option"]')].map(row => ({
        row: rect(row)!, title: rect(row.querySelector('.chat-search-row-title'))!, excerpt: rect(row.querySelector('.chat-search-row-excerpt')),
        date: rect(row.querySelector('time')), icon: rect(row.querySelector('.chat-search-icon'))!,
      })),
    }
  })
}

test.describe('normalized reference raster scale', () => {
  test.use({ deviceScaleFactor: 1.3 })
  test('search at inferred screenshot scale', async ({ page }, info) => {
    test.skip(info.project.name !== 'desktop', 'Explicit inferred raster scale')
    await page.setViewportSize({ width: 1477, height: 750 })
    const snapshot = savedChat()
    snapshot.conversations.conversations = Object.fromEntries(Object.entries(snapshot.conversations.conversations).slice(0, 5))
    for (const [index, conversation] of Object.values(snapshot.conversations.conversations).entries()) {
      conversation.title = ['Ideen gemeinsam weiterentwickeln', 'Eine technische Frage klären', 'Unser nächstes Projekt planen', 'Notizen zur Recherche', 'Einen neuen Ansatz ausprobieren'][index]!
      const id = conversation.id === 'main' ? 'user-0' : `fixture-user-${conversation.id}`
      snapshot.messages[id] = { id, conversationId: conversation.id, parentMessageId: null, role: 'user', content: 'Bei der Suche nach einem guten Ansatz hilft eine klare Frage.', createdAt: conversation.createdAt, status: 'completed' }
      conversation.activeLeafMessageId = id
    }
    await seedChat(page, snapshot)
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    await page.keyboard.press('Control+k')
    await page.locator('#chat-search-input').fill('suche')
    await expect(page.getByRole('option')).toHaveCount(5)
    await mkdir(evidence, { recursive: true })
    await page.screenshot({ path: resolve(evidence, 'reference-scale.png'), caret: 'hide' })
    await writeFile(resolve(evidence, 'reference-scale.json'), JSON.stringify(await searchGeometry(page.locator('.chat-search-dialog')), null, 2))
  })
})

for (const [width, height] of [[1701, 863], [1440, 900], [390, 844]] as const) for (const theme of ['light', 'dark']) for (const count of [1, 5, 50]) {
  test(`search layout ${count} results ${width} ${theme}`, async ({ page }, info) => {
    test.skip(info.project.name !== 'desktop', 'Explicit viewport and DPR matrix')
    await page.setViewportSize({ width, height })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    const snapshot = savedChat()
    const original = snapshot.conversations.conversations.main!
    snapshot.conversations.conversations = {}
    snapshot.messages = {}
    for (let index = 0; index < count; index++) {
      const id = index === 0 ? 'main' : `conversation-${index}`
      snapshot.conversations.conversations[id] = { ...original, id, title: index === 0 ? ('Treffer ' + 'Sehr langer Titel '.repeat(20)).slice(0, 120) : `Treffer ${index + 1}`, activeLeafMessageId: `message-${index}` }
      snapshot.messages[`message-${index}`] = {
        id: `message-${index}`, conversationId: id, parentMessageId: null, role: 'user', status: 'completed', createdAt: original.createdAt,
        content: `TREFFER ${index}: <img src=x onerror=alert(1)> ÄÖÜ Straße 👩🏽‍💻 e\u0301\n` + 'Ein langer passender Beschreibungstext auf mehreren Zeilen. '.repeat(index % 3 === 0 ? 30 : 2),
      }
    }
    await seedChat(page, snapshot, theme)
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    await page.keyboard.press('Control+k')
    const dialog = page.locator('.chat-search-dialog')
    const input = dialog.locator('input')
    await input.fill('treffer')
    await expect(dialog.getByRole('option')).toHaveCount(count)
    const metrics = await searchGeometry(dialog)
    await mkdir(evidence, { recursive: true })
    await writeFile(resolve(evidence, `${width}-${theme}-${count}.json`), JSON.stringify(metrics, null, 2))
    await page.screenshot({ path: resolve(evidence, `${width}-${theme}-${count}.png`), caret: 'hide' })
    if (phase === 'before') return
    expect(metrics.dialog!.width).toBe(Math.min(720, width - 32))
    expect(metrics.dialog!.height).toBe(460)
    expect(metrics.dialog!.x + metrics.dialog!.width / 2).toBeCloseTo(width / 2, 0)
    for (const [index, item] of metrics.rows.entries()) {
      expect(item.row.height).toBeGreaterThanOrEqual(64)
      if (index) expect(metrics.rows[index - 1]!.row.bottom).toBeLessThanOrEqual(item.row.top)
      expect(item.excerpt).not.toBeNull()
      expect(item.title.bottom).toBeLessThanOrEqual(item.excerpt!.top)
      expect(item.excerpt!.height).toBeLessThanOrEqual(40)
      expect(item.excerpt!.bottom).toBeLessThanOrEqual(item.row.bottom)
      expect(item.date).not.toBeNull()
      expect(item.title.right).toBeLessThanOrEqual(item.date!.left)
      expect(item.date!.right).toBeLessThanOrEqual(item.row.right)
      expect(Math.abs(item.icon.y + item.icon.height / 2 - item.row.y - item.row.height / 2)).toBeLessThanOrEqual(0.5)
    }
    await expect(dialog.locator('img')).toHaveCount(0)
    await expect(dialog.locator('mark').first()).toHaveText(/treffer/i)
    await expect(dialog.locator('.chat-search-row-title').first()).toHaveCSS('text-overflow', 'ellipsis')
    const categories = dialog.getByRole('navigation', { name: 'Suchkategorien' })
    await categories.getByRole('button', { name: 'Chats', exact: true }).click()
    await expect(dialog.getByRole('option')).toHaveCount(count)
    for (const name of ['Bilder', 'Dokumente', 'Pages', 'Projekte']) await expect(categories.getByRole('button', { name, exact: true })).toBeDisabled()
    await categories.getByRole('button', { name: 'Alle', exact: true }).click()
    await input.fill('nichtvorhanden')
    await expect(dialog.getByText('Keine Chats gefunden', { exact: true })).toBeVisible()
    await dialog.getByRole('button', { name: 'Löschen', exact: true }).click()
    await expect(dialog).toBeVisible()
    await expect(input).toHaveValue('')
    await expect(input).toBeFocused()
    await input.fill('treffer')
    await dialog.getByRole('option').last().scrollIntoViewIfNeeded()
    await expect(input).toBeInViewport()
    await expect(categories).toBeInViewport()
    expect(await dialog.evaluate(el => el.scrollHeight <= el.clientHeight)).toBe(true)
    expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
    expect(await categories.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
    expect(await dialog.locator('.chat-search-content').evaluate(el => el.scrollHeight <= el.clientHeight)).toBe(true)
    expect(await dialog.locator('.chat-search-viewport').evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
    await page.setViewportSize({ width, height: 320 })
    await expect(input).toBeInViewport()
    expect((await dialog.boundingBox())!.height).toBeLessThanOrEqual(288)
  })
}
