import { expect } from '@playwright/test'
import type { Page } from '@playwright/test'

export async function selectText(page: Page, selector: string, endSelector?: string, touch = false): Promise<string> {
  await page.locator(selector).first().scrollIntoViewIfNeeded()
  const text = await page.evaluate(({ startSelector, endSelector, touch }) => {
    const start = document.querySelector(startSelector)!
    const end = document.querySelector(endSelector ?? startSelector)!
    start.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerType: touch ? 'touch' : 'mouse' }))
    const range = document.createRange()
    range.setStart(start, 0)
    range.setEnd(end, end.childNodes.length)
    const selection = window.getSelection()!
    selection.removeAllRanges()
    selection.addRange(range)
    end.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, pointerType: touch ? 'touch' : 'mouse' }))
    return selection.toString()
  }, { startSelector: selector, ...(endSelector ? { endSelector } : {}), touch })
  await expect(page.getByRole('button', { name: 'noris AI fragen', exact: true })).toBeVisible()
  return text
}
