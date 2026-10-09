import { describe, expect, it } from 'vitest'
import { computed, ref } from 'vue'
import { indexSiblingVariants, siblingVariants } from '../../app/lib/chat/branches'
import type { ChatMessage, MessageRecords } from '../../app/lib/chat/types'

function message(id: string, conversationId: string, parentMessageId: string | null, role: ChatMessage['role'], createdAt = '2026-10-09T12:00:00Z'): ChatMessage {
  return { id, conversationId, parentMessageId, role, createdAt, content: id, status: 'completed' }
}

describe('branch metadata index', () => {
  it('preserves chronological and stable sibling order across conversations, roles and parents', () => {
    const nodes = [message('later', 'one', 'question', 'assistant', '2026-10-09T13:00:00Z'), message('first', 'one', 'question', 'assistant'), message('second', 'one', 'question', 'assistant'), message('other-chat', 'two', 'question', 'assistant'), message('other-parent', 'one', 'elsewhere', 'assistant'), message('other-role', 'one', 'question', 'user')]
    const records: MessageRecords = Object.fromEntries(nodes.map(node => [node.id, node]))
    const index = indexSiblingVariants(records)
    for (const node of nodes) expect(index.get(node.id)).toEqual(siblingVariants(records, node.id))
    expect(index.get('later')?.map(node => node.id)).toEqual(['first', 'second', 'later'])
    expect(index.get('unknown')).toBeUndefined()
  })

  it('orders server timezone offsets and optimistic UTC timestamps by actual time', () => {
    const first = message('server', 'chat', 'question', 'assistant', '2026-10-09T19:00:00+02:00')
    const later = message('browser', 'chat', 'question', 'assistant', '2026-10-09T17:00:01.000Z')
    const records = { server: first, browser: later }
    expect(indexSiblingVariants(records).get('browser')?.map(m => m.id)).toEqual(['server', 'browser'])
    expect(siblingVariants(records, 'browser').map(m => m.id)).toEqual(['server', 'browser'])
  })

  it('keeps conversation and parent keys unambiguous for arbitrary valid identifiers', () => {
    const nodes = [message('root-one', 'a:b', null, 'user'), message('root-two', 'a', null, 'user'), message('child-one', 'a:b', 'c', 'assistant'), message('child-two', 'a', 'b:c', 'assistant')]
    const index = indexSiblingVariants(Object.fromEntries(nodes.map(node => [node.id, node])))
    for (const node of nodes) expect(index.get(node.id)).toEqual([node])
  })

  it('retains cached membership during streaming and refreshes it when a variant is appended', () => {
    const records = ref<MessageRecords>({ first: message('first', 'chat', 'question', 'assistant') })
    const index = computed(() => indexSiblingVariants(records.value))
    const before = index.value
    const siblings = before.get('first')
    records.value.first!.content += ' streamed text'
    records.value.first!.status = 'streaming'
    expect(index.value).toBe(before)
    expect(index.value.get('first')).toBe(siblings)
    expect(siblings?.[0]?.content).toContain('streamed text')
    records.value = { ...records.value, second: message('second', 'chat', 'question', 'assistant') }
    expect(index.value).not.toBe(before)
    expect(index.value.get('second')?.map(node => node.id)).toEqual(['first', 'second'])
  })
})
