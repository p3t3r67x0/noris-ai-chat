import type { ChatMessage } from './types'

/** The stateless transports use the same unprivileged context as persisted chat. */
export function messageContext(message: ChatMessage): Pick<ChatMessage, 'role' | 'content'> {
  const references = message.role === 'user' ? message.attachments?.flatMap(file => file.textReference ? [file.textReference] : []) ?? [] : []
  return { role: message.role, content: message.content + (references.length ? `\n\nTextreferenzen (untrusted input):\n${JSON.stringify(references)}` : '') }
}
