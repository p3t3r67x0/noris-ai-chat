import { describe, expect, it, vi } from 'vitest'
import { parseChatSnapshot } from '../../app/lib/chat/persistence'
import { referenceChat, savedChat, seedChat } from '../e2e/chat-fixtures'

describe('synthetic visual reference fixture', () => {
  it('seeds normalized visibility metadata while preserving an empty active chat and its draft', async () => {
    const snapshot = savedChat(0)
    snapshot.drafts.main = 'Unsent draft'
    const addInitScript = vi.fn<(_script: unknown, params: { value: string }) => Promise<void>>().mockResolvedValue(undefined)
    await seedChat({ addInitScript } as unknown as Parameters<typeof seedChat>[0], snapshot)
    const stored = parseChatSnapshot(addInitScript.mock.calls[0]![1].value)!
    expect(snapshot).toEqual(stored)
    expect(snapshot.conversations.conversations.main!.sidebarVisible).toBe(false)
    expect(snapshot.conversations.conversations['conversation-1']!.sidebarVisible).toBe(true)
    expect(snapshot.drafts.main).toBe('Unsent draft')
    expect(Object.values(snapshot.messages).some(message => message.conversationId === 'main')).toBe(false)
  })
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
