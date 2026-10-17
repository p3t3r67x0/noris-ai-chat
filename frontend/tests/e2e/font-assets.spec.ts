import { expect, test } from '@playwright/test'
import { writeFile } from 'node:fs/promises'

test('uses the bundled UI and code faces at their actual weights', async ({ page }, info) => {
  await page.goto('/')
  await expect(page.locator('.chat-workspace')).toHaveAttribute('data-ready', 'true')
  await page.evaluate(async () => {
    for (const weight of [400, 500, 600, 700]) {
      const node = document.createElement('p')
      node.id = `font-probe-${weight}`
      node.style.fontWeight = String(weight)
      node.textContent = 'Synthetische Schriftprüfung ÄÖÜ 123'
      document.body.append(node)
    }
    const code = document.createElement('code')
    code.id = 'font-probe-mono'
    code.textContent = 'console.log("Noris")'
    document.body.append(code)
    await Promise.all([400, 500, 600, 700].map(weight => document.fonts.load(`${weight} 16px "Noris Sans"`)))
    await document.fonts.load('16px "Noris Mono"')
    await document.fonts.ready
  })
  const session = await page.context().newCDPSession(page)
  await session.send('DOM.enable')
  await session.send('CSS.enable')
  const documentTree = await session.send('DOM.getDocument')
  const measured: Record<string, unknown> = {}
  for (const face of ['400', '500', '600', '700', 'mono']) {
    const node = await session.send('DOM.querySelector', { nodeId: documentTree.root.nodeId, selector: `#font-probe-${face}` })
    const result = await session.send('CSS.getPlatformFontsForNode', { nodeId: node.nodeId })
    const used = result.fonts.filter(font => font.glyphCount > 0)
    expect(used.length).toBeGreaterThan(0)
    expect(used.every(font => font.isCustomFont && font.familyName.startsWith('Noris '))).toBe(true)
    measured[face] = result.fonts
  }
  const path = info.outputPath('fonts-used.json')
  await writeFile(path, JSON.stringify(measured, null, 2) + '\n')
  await info.attach('fonts-used', { path, contentType: 'application/json' })
})
