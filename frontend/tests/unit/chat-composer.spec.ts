import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import ChatComposer from '../../app/components/chat/ChatComposer.vue'

// Application boundaries are tested here; actual Nuxt UI keyboard/IME behavior is exercised in Playwright.
const Prompt = defineComponent({ emits: ['submit'], setup: (_, { emit, slots }) => () => h('form', { onSubmit: (event: Event) => { event.preventDefault(); emit('submit', event) } }, [slots.header?.(), slots.default?.(), slots.footer?.()]) })
function composer(modelValue: string, busy = false) {
  return mount(ChatComposer, { props: { modelValue, model: 'balanced', busy, streaming: busy, cancellationRequested: false }, global: { stubs: { UChatPrompt: Prompt, UButton: true, USelectMenu: true, UChatPromptSubmit: true } } })
}

afterEach(() => vi.unstubAllGlobals())

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
  it('keeps web search inside the input slot and removes it without editing the draft', async () => {
    const wrapper = composer('Mein Entwurf')
    await wrapper.setProps({ research: true, researchAvailable: true })
    expect(wrapper.get('[data-research-selected]').text()).toContain('Websuche')
    expect(wrapper.find('.composer-files').exists()).toBe(false)
    await wrapper.get('[aria-label="Websuche deaktivieren"]').trigger('click')
    expect(wrapper.emitted('update:research')).toEqual([[false]])
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    wrapper.unmount()
  })
  it('retains the research guard and the same send boundary', async () => {
    const wrapper = composer('Meine Recherche')
    await wrapper.setProps({ research: true, researchAvailable: true, researchError: 'Nicht verfügbar' })
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('send')).toBeUndefined()
    await wrapper.setProps({ researchError: null })
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('send')).toEqual([['Meine Recherche']])
    wrapper.unmount()
  })
  it('stops dictation when switching conversations or leaving the composer', async () => {
    const abort = vi.fn()
    vi.stubGlobal('SpeechRecognition', class {
      start = vi.fn()
      abort = abort
    })
    const wrapper = composer('Mein Entwurf')
    await wrapper.get('[aria-label="Diktieren"]').trigger('click')
    expect(wrapper.get('[aria-label="Diktat beenden"]').attributes('aria-pressed')).toBe('true')
    await wrapper.setProps({ conversationId: 'another-conversation' })
    expect(abort).toHaveBeenCalledTimes(1)
    await wrapper.get('[aria-label="Diktieren"]').trigger('click')
    await wrapper.get('.composer-container').trigger('focusout', { relatedTarget: document.createElement('button') })
    expect(abort).toHaveBeenCalledTimes(2)
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
