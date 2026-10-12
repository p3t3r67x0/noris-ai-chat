import { afterEach, describe, expect, it, vi } from 'vitest'
import { createChatState, useChat } from '../../app/composables/useChat'
import { supportsPreference } from '../../app/lib/chat/reasoning'
import { CHAT_STORAGE_KEY, parseChatSnapshot } from '../../app/lib/chat/persistence'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { ChatBackend } from '../../app/lib/chat/backend'
import type { ChatTransport } from '../../app/lib/chat/types'

const transport: ChatTransport = { async *stream() { yield { seq: 1, type: 'response.started' }; yield { seq: 2, type: 'response.completed' } } }
afterEach(() => localStorage.clear())

describe('conversation learning mode', () => {
  it('preserves a new draft, sends no message and persists activation through reload', async () => {
    const wrapper = mount(defineComponent({ setup: () => useChat(transport), render: () => h('div') }))
    wrapper.vm.drafts.draft.value = '  Mein Lernziel\nmit Kontext  '
    expect(await wrapper.vm.setConversationMode('learning')).toBe(true)
    expect(wrapper.vm.drafts.draft.value).toBe('  Mein Lernziel\nmit Kontext  ')
    expect(wrapper.vm.visible).toHaveLength(0)
    window.dispatchEvent(new Event('pagehide'))
    const saved = parseChatSnapshot(localStorage.getItem(CHAT_STORAGE_KEY)!)!
    const active = saved.conversations.conversations[saved.conversations.activeConversationId!]!
    expect(active.conversationMode).toBe('learning')
    wrapper.unmount()
    const reloaded = mount(defineComponent({ setup: () => useChat(transport), render: () => h('div') }))
    expect(reloaded.vm.conversations.active.value?.conversationMode).toBe('learning')
    expect(reloaded.vm.drafts.draft.value).toBe('  Mein Lernziel\nmit Kontext  ')
    await reloaded.vm.setConversationMode('normal')
    expect(reloaded.vm.conversations.active.value?.conversationMode).toBe('normal')
    reloaded.unmount()
  })
  it('keeps the mode through edits and variants and scopes it to its conversation', async () => {
    const state = createChatState(transport)
    await state.setConversationMode('learning')
    const conversation = state.conversations.active.value!
    expect(state.send('Lernziel', 'balanced')).toBe(true)
    await vi.waitFor(() => expect(state.stream.busy.value).toBe(false))
    const input = state.visible.value[0]!
    expect(state.edit(input.id, 'Neues Lernziel', 'fast')).toBe(true)
    await vi.waitFor(() => expect(state.stream.busy.value).toBe(false))
    expect(state.selectVariant(input.id)).toBe(true)
    expect(conversation.conversationMode).toBe('learning')
    expect(Object.keys(state.messages.value)).toHaveLength(4)
    state.newChat()
    expect(state.conversations.active.value?.conversationMode ?? 'normal').toBe('normal')
    state.conversations.select(conversation.id)
    expect(state.conversations.active.value?.conversationMode).toBe('learning')
  })
  it('blocks sending during failed server persistence without claiming activation', async () => {
    const backend = new ChatBackend(vi.fn<typeof fetch>().mockRejectedValue(new Error('offline')))
    const state = createChatState({ ...transport, backend })
    state.drafts.draft.value = 'Entwurf'
    expect(await state.setConversationMode('learning')).toBe(false)
    expect(state.conversations.active.value?.conversationMode).not.toBe('learning')
    expect(state.settingsError.value).toBeTruthy()
    expect(state.send('Entwurf', 'balanced')).toBe(false)
    expect(state.drafts.draft.value).toBe('Entwurf')
  })
})

describe('reasoning preferences', () => {
  it('requires explicit fresh server capabilities', () => {
    const model = { id: 'gpt', label: 'GPT', description: '', reasoningPreferences: ['instant', 'medium', 'high'] as const }
    const supported = { ...model, reasoningPreferences: [...model.reasoningPreferences] }
    expect(supportsPreference(supported, 'high')).toBe(true)
    expect(supportsPreference(supported, 'very_high')).toBe(false)
    expect(supportsPreference(supported, 'pro')).toBe(false)
    expect(supportsPreference({ ...supported, disabled: true }, 'high')).toBe(false)
    expect(supportsPreference({ ...supported, virtual: true }, 'high')).toBe(false)
    expect(supportsPreference({ id: 'gpt', label: 'GPT', description: 'Reasoning' }, 'high')).toBe(false)
  })
})
