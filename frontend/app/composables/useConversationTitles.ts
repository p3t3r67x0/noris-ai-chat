import type { Conversation } from '../lib/chat/conversations'
import { validGeneratedTitle } from '../lib/chat/titles'
import type { ChatTransport, ConversationTitleRequest } from '../lib/chat/types'

export function createConversationTitles(transport: ChatTransport, get: (id: string) => Conversation | undefined, timeoutMs = 8000) {
  const pending = new Map<string, AbortController>()
  let disposed = false
  function cancel(id: string): void { pending.get(id)?.abort(); pending.delete(id) }
  function cancelAll(): void { for (const id of pending.keys()) cancel(id) }
  function dispose(): void { disposed = true; cancelAll() }

  async function generate(request: ConversationTitleRequest): Promise<void> {
    const conversation = get(request.conversationId)
    if (disposed || !transport.generateTitle || !conversation || conversation.titleSource !== 'fallback' || !conversation.titleGenerationAttempted || pending.has(conversation.id) || pending.size >= 2) return
    const controller = new AbortController()
    pending.set(conversation.id, controller)
    const timer = setTimeout(() => { if (pending.get(conversation.id) === controller) cancel(conversation.id) }, timeoutMs)
    try {
      const result = await transport.generateTitle(request, controller.signal)
      if (controller.signal.aborted || disposed || get(conversation.id) !== conversation || conversation.titleSource !== 'fallback') return
      if (result.conversationId !== request.conversationId || result.inputMessageId !== request.inputMessageId || !validGeneratedTitle(result.title)) return
      conversation.title = result.title
      conversation.titleSource = 'generated'
    }
    catch { /* A failed title keeps the fallback and never changes the chat stream. */ }
    finally {
      clearTimeout(timer)
      if (pending.get(conversation.id) === controller) pending.delete(conversation.id)
    }
  }
  return { generate, cancel, cancelAll, dispose }
}
