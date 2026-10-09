import { test } from '@playwright/test'
import { captureScene } from './reference-scenes'

test.use({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 })
for (const theme of ['light', 'dark']) {
  for (const scene of ['empty', 'active', 'drawer', 'streaming']) {
    test(`reference mobile ${scene} ${theme}`, async ({ page }, testInfo) => { await captureScene(page, testInfo, scene, theme) })
  }
}
