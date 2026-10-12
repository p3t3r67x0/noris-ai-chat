import { afterEach, describe, expect, it } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import ChatReasoningMenu from '../../app/components/chat/ChatReasoningMenu.vue'
import { CHAT_MODELS } from '../../app/composables/useModelSelection'
import type { ChatModel } from '../../app/composables/useModelSelection'
import { createChatState } from '../../app/composables/useChat'
import { reasoningChoices } from '../../app/lib/chat/reasoning'
import { parseConversationSnapshot } from '../../app/lib/chat/conversations'
import type { ChatTransport } from '../../app/lib/chat/types'

const gpt: ChatModel = { id: 'gpt', label: 'GPT-OSS 120B', description: '', reasoningPreferences: ['instant', 'medium', 'high'] }
const glm: ChatModel = { id: 'glm', label: 'GLM 5.2', description: '', reasoningPreferences: ['high', 'very_high'] }
const originalModels = CHAT_MODELS.map(model => ({ ...model }))
afterEach(() => { CHAT_MODELS.splice(0, CHAT_MODELS.length, ...originalModels) })
const Button = defineComponent({ setup: (_, { slots }) => () => h('button', slots.default?.()) })
function menu(model: ChatModel, preference: 'very_high' | 'pro' | 'high' | null = null) {
  return mount(ChatReasoningMenu, { props: { model, preference }, global: { stubs: { UDropdownMenu: defineComponent({ name: 'UDropdownMenu', props: ['items'], setup: (_, { slots }) => () => h('div', slots.default?.()) }), UButton: Button } } })
}
function choices(wrapper: ReturnType<typeof menu>) {
  return wrapper.findComponent({ name: 'UDropdownMenu' }).props('items') as { label?: string, checked?: boolean, onSelect?: () => void }[]
}

describe('model-specific reasoning selection', () => {
  it('offers only catalog-approved GPT and GLM choices with the provider default', () => {
    const wrapper = menu(gpt, 'high')
    expect(choices(wrapper).filter(item => item.label).map(item => item.label)).toEqual(['Sofort', 'Mittel', 'Hoch', 'Modellstandard'])
    expect(choices(wrapper).find(item => item.label === 'Hoch')?.checked).toBe(true)
    expect(reasoningChoices(glm).map(choice => choice.label)).toEqual(['Hoch', 'Sehr hoch'])
    wrapper.unmount()
  })
  it('keeps Sehr hoch and its trigger on one line and updates on model change', async () => {
    const wrapper = menu(glm, 'very_high')
    expect(wrapper.get('button').text()).toBe('Sehr hoch')
    expect(wrapper.get('button').classes()).toEqual(expect.arrayContaining(['whitespace-nowrap', 'inline-flex', 'items-center', 'shrink-0']))
    expect(wrapper.get('button span').classes()).toContain('whitespace-nowrap')
    await wrapper.setProps({ model: gpt })
    expect(wrapper.get('button').text()).toBe('Standard')
    expect(choices(wrapper).some(item => item.label === 'Sehr hoch')).toBe(false)
    expect(choices(wrapper).find(item => item.label === 'Modellstandard')?.checked).toBe(true)
    choices(wrapper).find(item => item.label === 'Hoch')?.onSelect?.()
    expect(wrapper.emitted('select')).toEqual([['high']])
    wrapper.unmount()
  })
  it.each([{ ...glm, disabled: true }, { ...glm, virtual: true }, { ...glm, reasoningPreferences: [] }])('hides the entire menu without confirmed usable choices: %j', (model) => {
    const wrapper = menu(model, 'very_high')
    expect(wrapper.find('button').exists()).toBe(false)
    wrapper.unmount()
  })
  it('uses the default for an invalid stored preference', () => {
    const wrapper = menu(glm, 'pro')
    expect(wrapper.get('button').text()).toBe('Standard')
    expect(choices(wrapper).find(item => item.label === 'Pro')).toBeUndefined()
    wrapper.unmount()
  })
  it.each(['max', 'unknown', 5, { effort: 'high' }])('discards an invalid saved preference while retaining the conversation: %j', (preference) => {
    const state = createChatState({ async *stream() {} })
    state.conversations.create()
    const snapshot = state.conversations.snapshot()
    const conversation = snapshot.conversations[snapshot.activeConversationId!]!
    const raw = JSON.stringify({ ...snapshot, conversations: { [conversation.id]: { ...conversation, reasoningPreference: preference } } })
    const restored = parseConversationSnapshot(raw)!
    expect(restored.activeConversationId).toBe(conversation.id)
    expect(restored.conversations[conversation.id]).toEqual({ ...conversation, conversationMode: 'normal', reasoningPreference: null })
  })
  it('clears incompatible preferences instead of restoring them on switching back and never sends them', async () => {
    CHAT_MODELS.splice(0, CHAT_MODELS.length, gpt, glm)
    const sent: (string | null | undefined)[] = []
    const transport: ChatTransport = { async *stream(request) { sent.push(request.reasoningPreference); yield { seq: 1, type: 'response.completed' } } }
    const state = createChatState(transport)
    await state.setReasoningPreference('very_high')
    await state.reconcileReasoningPreference(glm.id)
    expect(state.conversations.active.value?.reasoningPreference).toBe('very_high')
    await state.reconcileReasoningPreference(gpt.id)
    expect(state.conversations.active.value?.reasoningPreference).toBeNull()
    await state.reconcileReasoningPreference(glm.id)
    expect(state.conversations.active.value?.reasoningPreference).toBeNull()
    expect(state.send('Frage', gpt.id)).toBe(true)
    await flushPromises()
    expect(sent).toEqual([null])
    await state.setReasoningPreference('pro')
    expect(state.send('Weitere Frage', glm.id)).toBe(true)
    await flushPromises()
    expect(sent).toEqual([null, null])
  })
})
