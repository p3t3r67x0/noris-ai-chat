import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import ChatMessage from '../../app/components/chat/ChatMessage.vue'
import CodeBlock from '../../app/components/chat/CodeBlock.vue'
import type { ChatMessage as Message } from '../../app/lib/chat/types'
import { originalCode } from '../fixtures/markdown'

const Button = defineComponent({ inheritAttrs: false, props: ['label', 'icon', 'color', 'variant', 'size'], setup: (props, { attrs }) => () => h('button', attrs, props.label) })
const message: Message = { id: 'm', conversationId: 'c', parentMessageId: null, role: 'user', content: 'Mein Text\nmit Kontext', status: 'completed', createdAt: '2026-10-09T12:00:00Z' }
afterEach(() => { vi.unstubAllGlobals() })

describe('message actions', () => {
  it('renders a user message once and keeps attachment downloads outside assistant markup', async () => {
    const wrapper = mount(ChatMessage, { props: { message }, global: { stubs: { UButton: Button, MarkdownContent: true, UIcon: true } } })
    expect(wrapper.find('.assistant-content').exists()).toBe(false)
    expect(wrapper.get('.user-bubble').text()).toBe(message.content)
    await wrapper.setProps({ message: { ...message, attachments: [{ id: 'file-id', conversationId: 'c', messageId: 'm', originalFilename: 'synthetic.txt', mimeType: 'text/plain', sizeBytes: 4, sha256: 'a'.repeat(64), status: 'ready', extractionStatus: 'extracted', modelUsable: true, createdAt: message.createdAt }] } })
    expect(wrapper.find('.assistant-content').exists()).toBe(false)
    expect(wrapper.get('.message-attachments a').attributes('href')).toBe('/api/v1/chat/attachments/file-id/content')
    wrapper.unmount()
  })
  it('copies the original text and confirms success', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const wrapper = mount(ChatMessage, { props: { message }, global: { stubs: { UButton: Button } } })
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(writeText).toHaveBeenCalledWith(message.content)
    expect(wrapper.getComponent(Button).attributes('aria-label')).toBe('Nachricht kopiert')
    wrapper.unmount()
  })
  it('renders persisted image pixels using the authenticated preview and reports layout changes', async () => {
    const attachment = { id: 'image-id', conversationId: 'c', messageId: 'm', originalFilename: 'synthetic.png', mimeType: 'image/png', sizeBytes: 100, sha256: 'a'.repeat(64), status: 'stored' as const, extractionStatus: 'not_applicable' as const, modelUsable: true, createdAt: message.createdAt }
    const wrapper = mount(ChatMessage, { props: { message: { ...message, attachments: [attachment] } }, global: { stubs: { UButton: Button, UIcon: true } } })
    const preview = wrapper.get('.message-attachment-image')
    expect(preview.attributes('src')).toBe('/api/v1/chat/attachments/image-id/content?preview=true')
    expect(preview.attributes('alt')).toBe('Angehängtes Bild: synthetic.png')
    expect(preview.attributes('loading')).toBe('lazy')
    await preview.trigger('load')
    expect(wrapper.emitted('rendered')).toEqual([[]])
    expect(wrapper.get('.message-attachments a').attributes('href')).toBe('/api/v1/chat/attachments/image-id/content')
    await wrapper.setProps({ message: { ...message, role: 'assistant', attachments: [attachment] } })
    expect(wrapper.find('.message-attachment-image').exists()).toBe(false)
    wrapper.unmount()
  })
  it('keeps the original download available when a preview fails and supports retry', async () => {
    const attachment = { id: 'image-id', conversationId: 'c', messageId: 'm', originalFilename: 'synthetic.jpg', mimeType: 'image/jpeg', sizeBytes: 100, sha256: 'a'.repeat(64), status: 'stored' as const, extractionStatus: 'not_applicable' as const, modelUsable: true, createdAt: message.createdAt }
    const wrapper = mount(ChatMessage, { props: { message: { ...message, attachments: [attachment] } }, global: { stubs: { UButton: Button, UIcon: true } } })
    await wrapper.get('.message-attachment-image').trigger('error')
    expect(wrapper.get('[role="status"]').text()).toContain('Bildvorschau konnte nicht geladen werden')
    expect(wrapper.find('.message-attachment-image').exists()).toBe(false)
    expect(wrapper.get('.message-attachments a').attributes('download')).toBeDefined()
    await wrapper.get('[aria-label="synthetic.jpg: Bildvorschau erneut laden"]').trigger('click')
    expect(wrapper.get('.message-attachment-image').attributes('src')).toBe('/api/v1/chat/attachments/image-id/content?preview=true')
    expect(wrapper.find('.message-image-error').exists()).toBe(false)
    wrapper.unmount()
  })
  it('reports unavailable clipboard access without pretending to copy', async () => {
    vi.stubGlobal('navigator', {})
    const wrapper = mount(ChatMessage, { props: { message }, global: { stubs: { UButton: Button } } })
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toContain('Kopieren nicht möglich')
    wrapper.unmount()
  })
  it('does not expose an incomplete message as a finished copy action', () => {
    const wrapper = mount(ChatMessage, { props: { message: { ...message, role: 'assistant', status: 'streaming' } }, global: { stubs: { UButton: Button, MarkdownContent: true } } })
    expect(wrapper.find('button').exists()).toBe(false)
    wrapper.unmount()
  })
  it('copies fenced code verbatim, including potentially dangerous text', async () => {
    const code = '<script>alert("x")</script>\n'
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const wrapper = mount(CodeBlock, { props: { code, language: 'unsupported' }, global: { stubs: { UButton: Button } } })
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(writeText).toHaveBeenCalledWith(code)
    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.get('code').text()).toContain('<script>')
    wrapper.unmount()
  })
  it('toggles code wrapping and copies unchanged source in both views', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const wrapper = mount(CodeBlock, { props: { code: originalCode, language: 'unsupported' }, global: { stubs: { UButton: Button } } })
    const toggle = wrapper.get('[aria-label="Zeilenumbruch umschalten"]')
    expect(toggle.attributes('aria-pressed')).toBe('true')
    expect(wrapper.get('figure').attributes('data-wrap')).toBe('true')
    expect(wrapper.get('code').element.textContent).toBe(originalCode)
    await wrapper.findAll('button')[0]!.trigger('click')
    await flushPromises()
    await toggle.trigger('click')
    expect(toggle.attributes('aria-pressed')).toBe('false')
    expect(wrapper.get('figure').attributes('data-wrap')).toBe('false')
    await wrapper.findAll('button')[0]!.trigger('click')
    await flushPromises()
    expect(writeText.mock.calls).toEqual([[originalCode], [originalCode]])
    await wrapper.setProps({ code: `${originalCode}# weiteres Streaming\n` })
    expect(toggle.attributes('aria-pressed')).toBe('false')
    expect(wrapper.get('code').element.textContent).toBe(`${originalCode}# weiteres Streaming\n`)
    await toggle.trigger('click')
    expect(toggle.attributes('aria-pressed')).toBe('true')
    wrapper.unmount()
  })
  it('emits edit and variant selection without changing the original message', async () => {
    const variant = { ...message, id: 'variant', content: 'Anderer Text' }
    const wrapper = mount(ChatMessage, { props: { message, variants: [message, variant] }, global: { stubs: { UButton: Button } } })
    await wrapper.get('[aria-label="Nachricht bearbeiten"]').trigger('click')
    await wrapper.get('[aria-label="Nächste Fragevariante"]').trigger('click')
    expect(wrapper.emitted('edit')).toEqual([[]])
    expect(wrapper.emitted('selectVariant')).toEqual([['variant']])
    expect(message.content).toBe('Mein Text\nmit Kontext')
    await wrapper.setProps({ busy: true })
    expect(wrapper.get('[aria-label="Nachricht bearbeiten"]').attributes()).toHaveProperty('disabled')
    expect(wrapper.get('[aria-label="Nächste Fragevariante"]').attributes()).toHaveProperty('disabled')
    wrapper.unmount()
  })
  it('emits regeneration for an assistant reply', async () => {
    const wrapper = mount(ChatMessage, { props: { message: { ...message, role: 'assistant' } }, global: { stubs: { UButton: Button, MarkdownContent: true } } })
    await wrapper.get('[aria-label="Antwort erneut generieren"]').trigger('click')
    expect(wrapper.emitted('regenerate')).toEqual([[]])
    expect(wrapper.find('[aria-label="Nachricht bearbeiten"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
