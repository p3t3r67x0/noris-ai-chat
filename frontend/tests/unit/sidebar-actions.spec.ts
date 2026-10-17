import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import ChatSidebar from '../../app/components/chat/ChatSidebar.vue'
import type { Conversation } from '../../app/lib/chat/conversations'

const chat: Conversation = { id: 'synthetic', title: 'Synthetischer Chat', titleSource: 'manual', titleGenerationAttempted: true, createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z', archivedAt: null, activeLeafMessageId: null }
const Button = defineComponent({ setup(_, { attrs, slots }) { return () => h('button', attrs, slots.default?.()) } })
const Sidebar = defineComponent({ setup(_, { slots }) { return () => h('aside', [slots.header?.(), slots.default?.(), slots.footer?.()]) } })
const Dropdown = defineComponent({ props: ['items'], emits: ['update:open'], setup(_, { slots, emit }) { const open = ref(false); return () => h('div', { onClick: () => { open.value = !open.value; emit('update:open', open.value) } }, slots.default?.()) } })
const wrappers: ReturnType<typeof mount>[] = []
afterEach(() => wrappers.splice(0).forEach(w => w.unmount()))
function fixture(conversation = chat, setPinned = vi.fn()) {
  const wrapper = mount(ChatSidebar, {
    props: { open: true, conversations: [conversation], archived: [], activeId: chat.id, removeConversation: vi.fn(), setPinned },
    global: { stubs: { USidebar: Sidebar, UButton: Button, UDropdownMenu: Dropdown, UModal: true, UInput: true, UColorModeSelect: true, ProfileMenu: true, ConversationTitle: false, ChatSearchDialog: true, DeleteConversationDialog: true } },
  })
  wrappers.push(wrapper)
  return { wrapper, setPinned }
}
describe('existing sidebar chat actions', () => {
  it('collapses recent rows without unmounting them or changing conversation state', async () => {
    const { wrapper } = fixture()
    const toggle = wrapper.get('.sidebar-section-toggle')
    const row = wrapper.get('[data-conversation-id="synthetic"]').element
    expect(toggle.text()).toContain('Letzte')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    const list = wrapper.get(`#${toggle.attributes('aria-controls')}`)
    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(list.attributes('style')).toContain('display: none')
    await wrapper.setProps({ conversations: [{ ...chat, title: 'Aktualisierter Titel' }] })
    await toggle.trigger('click')
    expect(wrapper.get('[data-conversation-id="synthetic"]').element).toBe(row)
    expect(wrapper.get('[data-conversation-id="synthetic"]').text()).toContain('Aktualisierter Titel')
    expect(wrapper.emitted('select')).toBeUndefined()
    expect(wrapper.emitted('newChat')).toBeUndefined()
  })
  it('keeps menu state and accessible labels associated with the same row', async () => {
    const { wrapper } = fixture()
    const row = wrapper.get('[data-conversation-id="synthetic"]')
    const button = row.get('[aria-label="Chat-Aktionen"]')
    expect(button.attributes('aria-haspopup')).toBe('menu')
    expect(button.attributes('aria-expanded')).toBe('false')
    await button.trigger('click')
    expect(button.attributes('aria-expanded')).toBe('true')
    expect(row.attributes('data-menu-open')).toBe('true')
    await button.trigger('click')
    expect(button.attributes('aria-expanded')).toBe('false')
    const menu = wrapper.findComponent(Dropdown)
    expect(menu.props('items').map((item: { label: string }) => item.label)).toEqual(['Umbenennen', 'Chat anpinnen', 'Archivieren', 'Löschen'])
  })
  it.each([false, true])('direct pin toggles the state independently from the menu: pinned=%s', async (pinned) => {
    const { wrapper, setPinned } = fixture({ ...chat, pinnedAt: pinned ? '2026-10-12T12:00:00Z' : null })
    await wrapper.get(`button[aria-label="${pinned ? 'Chat-Fixierung lösen' : 'Chat anpinnen'}"]`).trigger('click')
    await flushPromises()
    expect(setPinned).toHaveBeenCalledExactlyOnceWith(chat.id, !pinned)
    expect(wrapper.get('[data-conversation-id]').attributes('data-menu-open')).toBe('false')
    expect(wrapper.get('[role="status"]').text()).toContain(chat.title)
  })
  it('disables duplicate pin requests and reports a failed save without announcing success', async () => {
    let reject!: (cause: Error) => void
    const pending = new Promise<void>((_, no) => { reject = no })
    const { wrapper, setPinned } = fixture(chat, vi.fn(() => pending))
    const pin = wrapper.get('[aria-label="Chat anpinnen"]')
    await pin.trigger('click')
    expect(pin.attributes('disabled')).toBeDefined()
    reject(new Error('Conflict'))
    await flushPromises()
    expect(setPinned).toHaveBeenCalledOnce()
    expect(wrapper.get('[role="status"]').text()).toContain('nicht gespeichert')
    expect(pin.attributes('disabled')).toBeUndefined()
  })
})
