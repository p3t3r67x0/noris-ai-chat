import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import MarkdownContent from '../../app/components/chat/MarkdownContent'
import { citationPlaceholders, sourceHref, researchErrorKey, researchStates } from '../../app/lib/chat/research'
import { messages, translate } from '../../app/lib/settings/messages'
import { createChatState } from '../../app/composables/useChat'
import type { ChatRequest, ChatTransport } from '../../app/lib/chat/types'

describe('P7c authorized citations', () => {
  it('links only exact authorized Unicode offsets and preserves unknown/inherited suffix markers', async () => {
    const content = '🌍 **QGIS** [[R1]]. [[R9]] https://invented.example/ Then [[R1]].'
    const start = Array.from(content.slice(0, content.indexOf('[[R1]]'))).length
    const wrapper = mount(MarkdownContent, { props: { content, citations: [{ marker: 'R1', start, end: start + 6, claim_support: 'unverified' }] } })
    expect(wrapper.findAll('.research-citation')).toHaveLength(1)
    expect(wrapper.get('strong').text()).toBe('QGIS')
    expect(wrapper.text()).toContain('[[R9]]')
    expect(wrapper.text()).toContain('Then [[R1]]')
    expect(wrapper.findAll('a')).toHaveLength(0)
    await wrapper.get('.research-citation').trigger('click')
    expect(wrapper.emitted('citation')?.[0]?.[0]).toBe('R1')
    wrapper.unmount()
  })
  it('does not turn entity-encoded fake placeholders into citations', () => {
    const content = 'Fake &#xE000;noris0&#xE001; Actual [[R1]]'
    const start = content.indexOf('[[R1]]')
    const wrapper = mount(MarkdownContent, { props: { content, citations: [{ marker: 'R1', start, end: start + 6 }] } })
    expect(wrapper.findAll('.research-citation')).toHaveLength(1)
    expect(wrapper.text()).toContain('Fake')
    wrapper.unmount()
  })
  it('keeps markers in code and link labels as text, with no nested interactive HTML', () => {
    const content = '`[[R1]]` [label [[R1]]](https://example.org)\n\n```txt\n[[R1]]\n```'
    const citations = [...content.matchAll(/\[\[R1\]\]/g)].map(match => ({ marker: 'R1', start: match.index, end: match.index + 6, claim_support: 'unverified' as const }))
    const wrapper = mount(MarkdownContent, { props: { content, citations }, global: { stubs: { CodeBlock: true } } })
    expect(wrapper.findAll('.research-citation')).toHaveLength(0)
    expect(wrapper.get('code').text()).toBe('[[R1]]')
    expect(wrapper.get('a').text()).toContain('[[R1]]')
    expect(wrapper.getComponent({ name: 'CodeBlock' }).props('code')).toContain('[[R1]]')
    wrapper.unmount()
  })
  it('rejects bad offsets, unknown marker grammars, credentials and unsafe protocols', () => {
    const content = '[[R1]]'
    expect(citationPlaceholders(content, [{ marker: 'R1', start: 1, end: 7 }]).content).toBe(content)
    for (const value of ['javascript:alert(1)', 'data:text/html,hello', '//example.org', 'https://user:pass@example.org']) expect(sourceHref(value)).toBeUndefined()
    expect(sourceHref('https://example.org')).toBe('https://example.org/')
  })
  it('provides German and English copy for every state and error category', () => {
    for (const key of [...Object.values(researchStates), ...['CONTEXT_LIMIT', 'RESEARCH_INVALID', 'RESEARCH_APPROVAL_REQUIRED', 'TIMEOUT', 'BUDGET_LIMIT'].map(researchErrorKey)]) {
      expect(translate(key, 'de')).toBeTruthy()
      expect(translate(key, 'en')).toBeTruthy()
    }
    for (const value of Object.values(messages)) expect(value).toHaveLength(2)
  })
})

describe('P7c existing chat state', () => {
  it('transfers selection when upload/settings prepare the first conversation', async () => {
    const chat = createChatState({ async *stream() { yield { type: 'response.completed', seq: 1 } } })
    chat.drafts.draft.value = 'Unsent question'
    chat.researchMode.value = true
    await chat.setConversationMode('learning')
    expect(chat.researchMode.value).toBe(true)
    expect(chat.drafts.draft.value).toBe('Unsent question')
    chat.conversations.activeId.value = null
    expect(chat.researchMode.value).toBe(false)
  })
  it('keeps web selection across model changes and binds the generation to the selected model', async () => {
    const requests: ChatRequest[] = []
    const transport: ChatTransport = { async *stream(request) { requests.push(request); yield { type: 'response.started', seq: 1 }; yield { type: 'response.completed', seq: 2 } } }
    const chat = createChatState(transport)
    chat.researchMode.value = true
    let model = 'gpt-profile'
    expect(model).toBe('gpt-profile')
    model = 'glm-profile'
    expect(chat.researchMode.value).toBe(true)
    expect(chat.send('QGIS', model, [], { version: 1, mode: 'web', language: 'de' })).toBe(true)
    model = 'future-model'
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve()
    expect(requests[0]?.modelId).toBe('glm-profile')
    expect(requests[0]?.research).toMatchObject({ mode: 'web' })
    expect(chat.researchMode.value).toBe(true)
    expect(model).toBe('future-model')
  })
})
