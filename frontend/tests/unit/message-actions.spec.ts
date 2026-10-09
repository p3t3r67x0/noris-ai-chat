import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import ChatMessage from '../../app/components/chat/ChatMessage.vue'
import CodeBlock from '../../app/components/chat/CodeBlock.vue'
import type { ChatMessage as Message } from '../../app/lib/chat/types'

const Button = defineComponent({ inheritAttrs: false, props: ['label', 'icon', 'color', 'variant', 'size'], setup: (props, { attrs }) => () => h('button', attrs, props.label) })
const message: Message = { id: 'm', conversationId: 'c', parentMessageId: null, role: 'user', content: 'Mein Text\nmit Kontext', status: 'completed', createdAt: '2026-10-09T12:00:00Z' }
afterEach(() => { vi.unstubAllGlobals() })

describe('message actions', () => {
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
})
