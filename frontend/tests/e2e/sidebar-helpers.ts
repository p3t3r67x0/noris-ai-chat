import type { Page } from '@playwright/test'

export function conversationRow(page: Page, title: string) {
  return page.locator('.conversation-row:visible').filter({ has: page.getByRole('button', { name: title, exact: true }) })
}
export function chatActions(page: Page, title: string) {
  return conversationRow(page, title).getByRole('button', { name: 'Chat-Aktionen', exact: true })
}
export async function openChatActions(page: Page, title: string) {
  await conversationRow(page, title).hover()
  await chatActions(page, title).click()
}
