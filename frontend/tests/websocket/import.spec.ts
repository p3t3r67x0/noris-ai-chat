import { expect, test } from '@playwright/test'

test.beforeEach(async ({ request }) => {
  const response = await request.get('/api/v1/conversations?archived=true')
  expect(response.ok()).toBe(true)
  for (const c of (await response.json()).conversations) await request.delete(`/api/v1/conversations/${c.id}`)
  await request.put('/api/v1/chat/preferences', { data: { activeConversationId: null } })
})

test('imports only after explicit user action and retains the original browser backup', async ({ page, request }) => {
  const id = crypto.randomUUID(), user = crypto.randomUUID(), reply = crypto.randomUUID(), variant = crypto.randomUUID()
  const time = new Date().toISOString()
  const snapshot = { version: 1, conversations: { version: 1, activeConversationId: id, conversations: { [id]: { id, title: 'Lokaler Import', titleSource: 'manual', titleGenerationAttempted: true, createdAt: time, updatedAt: time, archivedAt: null, activeLeafMessageId: reply } } }, messages: {
    [user]: { id: user, conversationId: id, parentMessageId: null, role: 'user', content: 'Lokale Frage', status: 'completed', createdAt: time },
    [reply]: { id: reply, conversationId: id, parentMessageId: user, role: 'assistant', content: 'Lokale Antwort', status: 'completed', createdAt: time },
    [variant]: { id: variant, conversationId: id, parentMessageId: user, role: 'assistant', content: 'Andere Antwort', status: 'completed', createdAt: time },
  }, drafts: { [id]: 'Lokaler Entwurf' }, preferredLeaves: { [user]: reply } }
  const raw = JSON.stringify(snapshot)
  await page.addInitScript(value => localStorage.setItem('noris-ai:chat:v1', value), raw)
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Lokale Chats importieren' })).toBeVisible()
  expect((await request.get(`/api/v1/conversations/${id}`)).status()).toBe(404)
  await page.getByRole('button', { name: 'Lokale Chats importieren' }).click()
  await expect(page.getByRole('dialog')).toContainText('Die lokale Sicherung bleibt erhalten')
  expect((await request.get(`/api/v1/conversations/${id}`)).status()).toBe(404)
  await page.getByRole('button', { name: 'Import ausdrücklich starten' }).click()
  await expect(page.getByRole('alert')).toContainText('1 Chats importiert')
  const result = (await (await request.get(`/api/v1/conversations/${id}/messages`)).json()).messages
  expect(result.map((m: { id: string }) => m.id).sort()).toEqual([user, reply, variant].sort())
  expect(await page.evaluate(() => localStorage.getItem('noris-ai:chat:v1'))).toBe(raw)
  await expect(page.getByRole('textbox', { name: 'Nachricht' })).toHaveValue('Lokaler Entwurf')
})
