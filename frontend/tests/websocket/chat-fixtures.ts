import { expect } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'
import type { ApiSchemas } from '../../app/types/generated/api'

/** Keep verified metadata stable while testing tool/learning lifecycle, not expiry. */
export async function stableModelCatalog(page: Page): Promise<void> {
  await page.route('**/api/v1/llm/models', async (route) => {
    const response = await route.fetch()
    if (!response.ok()) {
      await route.fulfill({ response })
      return
    }
    // Preserve the real catalog, including availability and stale status. Only
    // its fixture timer changes; explicit focus refresh and server checks remain.
    await route.fulfill({ response, json: { ...await response.json(), expires_in_seconds: 60 } })
  })
}

/** Clear only the disposable browser-test database, including hidden preparations. */
export async function clearTestConversations(request: APIRequestContext): Promise<void> {
  for (const preparedOnly of [false, true]) {
    let cursor: string | null = null
    do {
      const response = await request.get('/api/v1/conversations', {
        params: { archived: true, preparedOnly, limit: 100, ...(cursor ? { cursor } : {}) },
      })
      expect(response.ok()).toBe(true)
      const page: ApiSchemas['ConversationListResponse'] = await response.json()
      for (const conversation of page.conversations) {
        expect((await request.delete(`/api/v1/conversations/${conversation.id}`)).ok()).toBe(true)
      }
      cursor = page.nextCursor ?? null
    } while (cursor)
  }
}
