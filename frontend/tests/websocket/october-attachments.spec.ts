import { expect, test } from '@playwright/test'
import { clearTestConversations, stableModelCatalog } from './chat-fixtures'

test.beforeEach(async ({ page, request }) => {
  await stableModelCatalog(page)
  await clearTestConversations(request)
  await request.put('/api/v1/chat/drafts/new', { data: { content: '' } })
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null, modelId: null } })
})

for (const theme of ['light', 'dark']) for (const width of [1701, 390]) {
  test(`October real attachments ${width} ${theme}`, async ({ page }, info) => {
    test.skip(info.project.name !== 'desktop', 'This matrix defines its own viewport; existing upload tests also run in the touch project.')
    await page.setViewportSize({ width, height: width === 390 ? 844 : 863 })
    await page.addInitScript(theme => localStorage.setItem('noris-ai-theme', theme), theme)
    await page.goto('/')
    await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
    const input = page.locator('.composer-input')
    await input.fill('Synthetischer Entwurf mit Anhängen')
    await input.evaluate(element => { element.dataset.retained = 'original' })
    const original = (await page.locator('.chat-composer').boundingBox())!
    let release!: () => void
    const held = new Promise<void>(resolve => { release = resolve })
    await page.route('**/api/v1/chat/attachments?*', async route => {
      if (route.request().method() === 'POST') await held
      await route.continue()
    })
    const file = (name: string) => ({ name, mimeType: 'text/plain', buffer: Buffer.from(`Synthetic local test content: ${name}`) })
    await page.locator('input[type="file"]').setInputFiles([file('synthetic-one.txt')])
    try {
      await expect(page.locator('[data-upload-status="uploading"]')).toHaveCount(1)
      await expect(page).toHaveScreenshot(`october-uploading-${width}-${theme}.png`, { animations: 'disabled' })
    }
    finally { release() }
    await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(1)
    await expect(page).toHaveScreenshot(`october-attachment-${width}-${theme}.png`, { animations: 'disabled' })
    await page.locator('input[type="file"]').setInputFiles([file('synthetic-two.txt')])
    await expect(page.locator('[data-upload-status="uploaded"]')).toHaveCount(2)
    await input.focus()
    await expect(page).toHaveScreenshot(`october-two-attachments-${width}-${theme}.png`, { animations: 'disabled' })
    const attached = (await page.locator('.chat-composer').boundingBox())!
    // Large file headers may consume the reserved empty-state space on mobile;
    // all controls and the same editor must remain visible and connected.
    expect(attached.height).toBeGreaterThan(original.height)
    await expect(input).toHaveAttribute('data-retained', 'original')
    await expect(input).toHaveValue('Synthetischer Entwurf mit Anhängen')
    await expect(page.locator('.composer-submit')).toBeInViewport()
    await expect(page.locator('.conversation-row')).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeEnabled()
    await input.press('Enter')
    await expect(page.locator('[data-generation-status="completed"]')).toBeAttached()
    await expect(input).toHaveAttribute('data-retained', 'original')
    await expect(input).toBeFocused()
    await expect(page.locator('.message-attachments a')).toHaveCount(2)
    await expect(page.locator('.attachment-preview')).toHaveCount(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
