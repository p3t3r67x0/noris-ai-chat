import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { useChat } from '../../app/composables/useChat'
import { CHAT_STORAGE_KEY, parseChatSnapshot } from '../../app/lib/chat/persistence'
import type { ChatTransport } from '../../app/lib/chat/types'

const transport: ChatTransport = { async *stream() { yield { seq: 1, type: 'response.started' }; yield { seq: 2, type: 'response.completed' } } }
function workspace() {
  return mount(defineComponent({ setup() { return useChat(transport) }, render() { return h('div') } }))
}
afterEach(() => { vi.useRealTimers(); localStorage.clear() })

describe('atomic persistence lifecycle', () => {
  it('flushes a new conversation and its latest draft together on pagehide', () => {
    vi.useFakeTimers()
    const wrapper = workspace()
    wrapper.vm.newChat()
    wrapper.vm.drafts.draft.value = 'Mein letzter Entwurf'
    window.dispatchEvent(new Event('pagehide'))
    const saved = parseChatSnapshot(localStorage.getItem(CHAT_STORAGE_KEY) ?? '')
    expect(saved).not.toBeNull()
    const id = saved!.conversations.activeConversationId!
    expect(saved!.conversations.conversations[id]?.title).toBe('Neuer Chat')
    expect(saved!.drafts[id]).toBe('Mein letzter Entwurf')
    wrapper.unmount()
  })
  it('does not overwrite external changes after another tab writes', async () => {
    vi.useFakeTimers()
    const wrapper = workspace()
    wrapper.vm.newChat()
    const external = 'external snapshot'
    localStorage.setItem(CHAT_STORAGE_KEY, external)
    window.dispatchEvent(new StorageEvent('storage', { key: CHAT_STORAGE_KEY, newValue: external }))
    wrapper.vm.drafts.draft.value = 'Lokaler Entwurf'
    await vi.runAllTimersAsync()
    window.dispatchEvent(new Event('pagehide'))
    expect(localStorage.getItem(CHAT_STORAGE_KEY)).toBe(external)
    expect(wrapper.vm.storageWarning).toContain('anderen Tab')
    wrapper.unmount()
  })
})
