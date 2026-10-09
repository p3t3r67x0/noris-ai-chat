import { describe, expect, it } from 'vitest'
import { parseChatSnapshot } from '../../app/lib/chat/persistence'
import { referenceChat } from '../e2e/chat-fixtures'

describe('synthetic visual reference fixture', () => {
  it('retains a valid normalized conversation and parent path', () => {
    const snapshot = referenceChat()
    const parsed = parseChatSnapshot(JSON.stringify(snapshot))
    expect(parsed).not.toBeNull()
    expect(parsed!.conversations.activeConversationId).toBe('main')
    expect(parsed!.conversations.conversations.main!.activeLeafMessageId).toBe('assistant-0')
    expect(parsed!.messages['assistant-0']!.parentMessageId).toBe('user-0')
    expect(parsed!.messages['user-0']!.parentMessageId).toBeNull()
    expect(parsed!.messages['assistant-0']!.status).toBe('completed')
  })

  it('uses synthetic history labels and only a reserved example URL', () => {
    const snapshot = referenceChat()
    for (const conversation of Object.values(snapshot.conversations.conversations)) {
      expect(conversation.title).toMatch(/^(Fiktiver Tagesplan|Beispiel \d+)$/)
    }
    const contents = Object.values(snapshot.messages).map(message => message.content).join('\n')
    const urls = contents.match(/https?:\/\/[^)\s]+/g) ?? []
    expect(urls.length).toBeGreaterThan(0)
    for (const url of urls) expect(new URL(url).hostname).toBe('example.com')
  })
})
