import { expect } from '@playwright/test'
import type { APIRequestContext } from '@playwright/test'
import type { ApiSchemas } from '../../app/types/generated/api'

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
