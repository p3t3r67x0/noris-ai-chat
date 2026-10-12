import type { Page } from '@playwright/test'
import { DEFAULT_CHAT_LIMITS } from '../../app/lib/chat/limits'
import type { ApiSchemas } from '../../app/types/generated/api'

export const conversationId = '10000000-0000-4000-8000-000000000001'
const date = '2026-10-12T10:00:00.000Z'
export async function notificationBackend(page: Page, options: { generationCode?: string, partial?: string, failUploads?: number, failSettings?: number, modelCode?: string, failDelete?: number, restoredDraft?: boolean, disconnect?: boolean } = {}) {
  const state = { generations: 0, resumes: 0, uploads: 0, settings: 0, deletes: 0, generationCode: options.generationCode ?? 'PROVIDER_UNREACHABLE' }
  let conversation: ApiSchemas['ConversationResponse'] = { id: conversationId, title: 'Benachrichtigungen prüfen', titleSource: 'manual', version: 1, activeLeafMessageId: '10000000-0000-4000-8000-000000000003', createdAt: date, updatedAt: date, archivedAt: null, lastMessageAt: date, conversationMode: 'normal', reasoningPreference: null }
  const messages: ApiSchemas['MessageResponse'][] = [
    { id: '10000000-0000-4000-8000-000000000002', conversationId, parentMessageId: null, role: 'user', content: 'Wie bleiben meine bisherigen Nachrichten erhalten?', status: 'completed', modelId: null, generationId: null, editedFromMessageId: null, createdAt: date, updatedAt: date },
    { id: conversation.activeLeafMessageId!, conversationId, parentMessageId: '10000000-0000-4000-8000-000000000002', role: 'assistant', content: 'Dein bisheriger Chat bleibt erhalten. Eine fehlgeschlagene Antwort kannst du gezielt erneut versuchen.', status: 'completed', modelId: 'fixture', generationId: null, editedFromMessageId: null, createdAt: date, updatedAt: date },
  ]
  const attachments: ApiSchemas['AttachmentResponse'][] = []
  await page.addInitScript(({ restoredDraft, id }) => {
    if (restoredDraft) localStorage.setItem('noris-ai:offline-drafts:v1', JSON.stringify({ [id]: 'Ein wiederhergestellter Entwurf.' }))
  }, { restoredDraft: options.restoredDraft ?? false, id: conversationId })
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url())
    const path = url.pathname.replace('/api/v1', '')
    const method = route.request().method()
    const body = route.request().headers()['content-type']?.includes('application/json') ? route.request().postDataJSON() as Record<string, unknown> | null : null
    const error = async (code: string, status = 503) => route.fulfill({ status, json: { error: { code, message: 'An internal error occurred; secret=DO_NOT_DISPLAY', request_id: '20000000-0000-4000-8000-000000000001' } }, headers: { 'X-Request-ID': '20000000-0000-4000-8000-000000000001' } })
    let json: unknown = {}
    if (path === '/llm/models') {
      if (options.modelCode) return error(options.modelCode)
      json = { models: [{ id: 'fixture', name: 'Testmodell', available: true, streaming: true }], default_model: 'fixture', limits: DEFAULT_CHAT_LIMITS }
    }
    else if (path === '/chat/ws-ticket') json = { ticketId: 'fixture-ticket' }
    else if (path === '/chat/preferences' && method === 'GET') json = { activeConversationId: conversationId, modelId: 'fixture' }
    else if (path === '/chat/drafts') json = { drafts: [] }
    else if (path === '/chat/attachments/limits') json = { maxFiles: 10, maxFileBytes: 10485760, maxReferenceChars: 32000, mimeTypes: ['text/plain', 'application/pdf'], visionSupported: false }
    else if (path === '/chat/attachments' && method === 'GET') json = { attachments }
    else if (path === '/chat/attachments' && method === 'POST') {
      state.uploads++
      if (state.uploads <= (options.failUploads ?? 0)) return error('ATTACHMENT_UPLOAD_TIMEOUT', 504)
      const attachment: ApiSchemas['AttachmentResponse'] = { id: '10000000-0000-4000-8000-000000000004', conversationId, messageId: null, originalFilename: url.searchParams.get('filename')!, mimeType: 'text/plain', sizeBytes: 12, sha256: 'a'.repeat(64), status: 'ready', extractionStatus: 'extracted', modelUsable: true, createdAt: date }
      attachments.push(attachment)
      return route.fulfill({ status: 201, json: attachment })
    }
    else if (path === '/conversations') json = { conversations: conversation ? [conversation] : [], nextCursor: null, hasMore: false }
    else if (path.endsWith('/active-path')) json = { conversation, messages, variants: [], leafMessageId: conversation.activeLeafMessageId, boundaryParentId: null, hasMore: false, nextCursor: null }
    else if (path === `/conversations/${conversationId}` && method === 'PATCH') {
      state.settings++
      if (state.settings <= (options.failSettings ?? 0)) return error('INTERNAL_ERROR')
      conversation = { ...conversation, ...body, version: conversation.version + 1 } as typeof conversation
      json = conversation
    }
    else if (path === `/conversations/${conversationId}` && method === 'DELETE') {
      state.deletes++
      if (state.deletes <= (options.failDelete ?? 0)) return error('INTERNAL_ERROR')
      return route.fulfill({ status: 204 })
    }
    else if (path === `/conversations/${conversationId}`) json = conversation
    else if (method === 'PUT') return route.fulfill({ status: 204 })
    await route.fulfill({ json })
  })
  await page.routeWebSocket('**/api/v1/chat/ws', socket => {
    socket.onMessage(raw => {
      const command = JSON.parse(String(raw)) as Record<string, string>
      if (command.type === 'chat.ping') return
      if (command.type === 'chat.resume') {
        state.resumes++
        const reply = messages.find(message => message.generationId === command.generationId)!
        reply.status = 'completed'
        socket.send(JSON.stringify({ version: 1, type: 'chat.resume.snapshot', generationId: command.generationId, conversationId, messageId: reply.id, content: reply.content, status: 'completed', lastSequence: 3, continuationCount: 0 }))
        return
      }
      if (command.type !== 'chat.generate') return
      state.generations++
      const seq = { version: 1, conversationId, generationId: command.requestId, messageId: command.assistantMessageId, continuationCount: 0 }
      const partial = options.partial ?? 'Diese Teilantwort bleibt bei einem Verbindungsfehler erhalten.'
      const failed = state.generations === 1 && Boolean(state.generationCode)
      const reply: ApiSchemas['MessageResponse'] = { id: command.assistantMessageId!, conversationId, parentMessageId: command.inputMessageId!, role: 'assistant', content: failed ? partial : 'Die erneut angeforderte Antwort wurde erfolgreich erstellt.', status: failed ? 'failed' : 'completed', generationId: command.requestId!, modelId: 'fixture', editedFromMessageId: null, createdAt: date, updatedAt: date, ...(failed ? { errorCode: state.generationCode, errorMessage: 'An internal error occurred' } : {}) }
      if (!messages.some(message => message.id === command.inputMessageId)) messages.push({ id: command.inputMessageId!, conversationId, parentMessageId: command.parentMessageId ?? null, role: 'user', content: command.content!, status: 'completed', modelId: null, generationId: null, editedFromMessageId: null, createdAt: date, updatedAt: date })
      messages.push(reply)
      conversation.activeLeafMessageId = reply.id
      socket.send(JSON.stringify({ ...seq, type: 'chat.generation.started', seq: 1 }))
      if (reply.content) socket.send(JSON.stringify({ ...seq, type: 'chat.generation.delta', seq: 2, delta: reply.content }))
      if (options.disconnect) {
        reply.status = 'streaming'
        setTimeout(() => { socket.close({ code: 1001, reason: 'local reconnect fixture' }) }, 50)
        return
      }
      socket.send(JSON.stringify({ ...seq, seq: reply.content ? 3 : 2, type: failed ? 'chat.generation.failed' : 'chat.generation.completed', content: reply.content, ...(failed ? { code: state.generationCode, message: 'An internal error occurred; secret=DO_NOT_DISPLAY' } : {}) }))
    })
  })
  return state
}
