import type { Page } from '@playwright/test'
import type { ChatSnapshot } from '../../app/lib/chat/persistence'
import { CHAT_STORAGE_KEY } from '../../app/lib/chat/persistence'

export function savedChat(turns = 1): ChatSnapshot {
  const date = '2026-10-09T12:00:00.000Z'
  const snapshot: ChatSnapshot = {
    version: 1, conversations: { version: 1, activeConversationId: 'main', conversations: {} }, messages: {}, drafts: {}, preferredLeaves: {},
  }
  for (let index = 0; index < 45; index++) {
    const id = index === 0 ? 'main' : `conversation-${index}`
    snapshot.conversations.conversations[id] = { id, title: index === 0 ? 'Unser Gespräch' : `Gedanken ${index}`, createdAt: date, updatedAt: date, archivedAt: null, activeLeafMessageId: null }
  }
  for (let index = 0; index < turns; index++) {
    const user = `user-${index}`, assistant = `assistant-${index}`
    snapshot.messages[user] = { id: user, conversationId: 'main', parentMessageId: index ? `assistant-${index - 1}` : null, role: 'user', content: index ? `Frage ${index + 1}` : 'Wie können wir eine gute Idee weiterentwickeln?', status: 'completed', createdAt: date }
    snapshot.messages[assistant] = { id: assistant, conversationId: 'main', parentMessageId: user, role: 'assistant', content: '### Ein guter Anfang\n\nBeginne mit einer klaren Frage. Halte fest, für wen deine Idee hilfreich ist.\n\n1. Beschreibe dein Ziel.\n2. Probiere einen kleinen Schritt aus.\n3. Prüfe, was du gelernt hast.\n\n**Wir können gemeinsam daran weiterarbeiten.**', status: 'completed', createdAt: date }
    snapshot.conversations.conversations.main!.activeLeafMessageId = assistant
  }
  return snapshot
}
export async function seedChat(page: Page, snapshot: ChatSnapshot, theme = 'light') {
  await page.addInitScript(({ key, value, selectedTheme }) => {
    localStorage.setItem(key, value)
    localStorage.setItem('noris-ai-theme', selectedTheme)
  }, { key: CHAT_STORAGE_KEY, value: JSON.stringify(snapshot), selectedTheme: theme })
}
