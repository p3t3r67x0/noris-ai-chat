import type { Page } from '@playwright/test'

export function conversationRow(page: Page, title: string) {
  // The fitted caption can shorten on hover; the authoritative title stays stable.
  return page.locator('.conversation-row:visible').filter({ has: page.getByTitle(title, { exact: true }) })
}
export function chatActions(page: Page, title: string) {
  return conversationRow(page, title).getByRole('button', { name: 'Chat-Aktionen', exact: true })
}
export async function openChatActions(page: Page, title: string) {
  await conversationRow(page, title).hover()
  await chatActions(page, title).click()
}
