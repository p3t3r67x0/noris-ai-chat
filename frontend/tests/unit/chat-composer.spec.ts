import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import ChatComposer from '../../app/components/chat/ChatComposer.vue'

// Application boundaries are tested here; actual Nuxt UI keyboard/IME behavior is exercised in Playwright.
const Prompt = defineComponent({ emits: ['submit'], setup: (_, { emit, slots }) => () => h('form', { onSubmit: (event: Event) => { event.preventDefault(); emit('submit', event) } }, [slots.header?.(), slots.footer?.()]) })
function composer(modelValue: string, busy = false) {
  return mount(ChatComposer, { props: { modelValue, model: 'balanced', busy, streaming: busy, cancellationRequested: false }, global: { stubs: { UChatPrompt: Prompt, UButton: true, USelectMenu: true, UChatPromptSubmit: true } } })
}

describe('composer application behavior', () => {
  it('emits the draft only for valid input and preserves the original whitespace', async () => {
    const wrapper = composer('  Eine Frage\nmit Kontext  ')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('send')).toEqual([['  Eine Frage\nmit Kontext  ']])
    wrapper.unmount()
  })
  it.each(['   ', 'x'.repeat(32_001)])('does not send empty or oversized drafts', async (value) => {
    const wrapper = composer(value)
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('send')).toBeUndefined()
    wrapper.unmount()
  })
  it('keeps an editable draft while streaming but blocks another submission', async () => {
    const wrapper = composer('Meine nächste Frage', true)
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('send')).toBeUndefined()
    expect(wrapper.findComponent({ name: 'UChatPromptSubmit' }).attributes('aria-label')).toBe('Antwort stoppen')
    wrapper.unmount()
  })
  it('passes multiple native files to the existing attachment boundary without editing the draft', async () => {
    const wrapper = composer('Mein Entwurf')
    const input = wrapper.get('input[type="file"]')
    const selected = [new File(['First'], 'first.txt', { type: 'text/plain' }), new File(['Second'], 'second.md', { type: 'text/markdown' })]
    expect(input.attributes('multiple')).toBeDefined()
    Object.defineProperty(input.element, 'files', { value: selected })
    await input.trigger('change')
    expect(wrapper.emitted('files')).toEqual([[selected]])
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    wrapper.unmount()
  })
  it('does not create an attachment conversation when native selection is empty or cancelled', async () => {
    const wrapper = composer('Mein Entwurf')
    await wrapper.get('input[type="file"]').trigger('change')
    await wrapper.get('input[type="file"]').trigger('cancel')
    expect(wrapper.emitted('files')).toBeUndefined()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    wrapper.unmount()
  })
})
