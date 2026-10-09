import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import DeleteConversationDialog from '../../app/components/chat/DeleteConversationDialog.vue'
import { createChatState } from '../../app/composables/useChat'
import { createMockTransport } from '../../app/lib/chat/mockTransport'
import type { Conversation } from '../../app/lib/chat/conversations'

// Test the application boundary here; Playwright exercises the real UModal.
const Modal = defineComponent({
  props: ['open', 'title', 'description', 'close', 'content', 'dismissible'], emits: ['update:open'],
  setup: (props, { emit, slots }) => () => props.open ? h('section', [
    h('h2', props.title), h('p', props.description),
    h('div', { onClick: () => emit('update:open', false) }, slots.close?.()),
    slots.body?.(), slots.footer?.({ close: () => emit('update:open', false) }),
  ]) : null,
})
const Button = defineComponent({
  props: ['label', 'disabled', 'loading'],
  setup: (props, { attrs }) => () => h('button', { ...attrs, disabled: props.disabled }, props.label),
})
const conversation: Conversation = { id: 'delete-me', title: 'Synthetische Statusübersicht', createdAt: '2026-10-09T12:00:00.000Z', updatedAt: '2026-10-09T12:00:00.000Z', archivedAt: null, activeLeafMessageId: null }
const wrappers: ReturnType<typeof mount>[] = []
afterEach(() => { wrappers.splice(0).forEach(wrapper => wrapper.unmount()); document.body.innerHTML = '' })
function dialog(removeConversation: (id: string) => void | Promise<void> = vi.fn(), target: Conversation | null = conversation, returnFocus?: HTMLElement) {
  const wrapper = mount(DeleteConversationDialog, {
    props: { conversation: target, removeConversation, open: true, ...(returnFocus ? { returnFocus } : {}), 'onUpdate:open': value => { void wrapper.setProps({ open: value }) } },
    global: { stubs: { UModal: Modal, UButton: Button } }, attachTo: document.body,
  })
  wrappers.push(wrapper)
  return wrapper
}

describe('delete conversation dialog', () => {
  it('opens with the selected title and renders untrusted long names as text', async () => {
    const title = '<img src=x onerror=alert(1)>' + 'a'.repeat(120)
    const wrapper = dialog(vi.fn(), { ...conversation, title })
    expect(wrapper.text()).toContain(`Dadurch wird ${title} endgültig gelöscht.`)
    expect(wrapper.find('img').exists()).toBe(false)
    await wrapper.setProps({ open: false })
    expect(wrapper.find('section').exists()).toBe(false)
  })

  it.each(['.delete-dialog-cancel', '[aria-label="Dialog schließen"]'])('cancels through %s without invoking deletion', async (selector) => {
    const remove = vi.fn()
    const wrapper = dialog(remove)
    await wrapper.get(selector).trigger('click')
    expect(wrapper.props('open')).toBe(false)
    expect(remove).not.toHaveBeenCalled()
  })

  it('waits for the selected ID, prevents duplicate confirmation and blocks dismissal while pending', async () => {
    let finish!: () => void
    const remove = vi.fn(() => new Promise<void>(resolve => { finish = resolve }))
    const wrapper = dialog(remove)
    await wrapper.get('.delete-dialog-confirm').trigger('click')
    await wrapper.get('.delete-dialog-confirm').trigger('click')
    const modal = wrapper.findComponent(Modal)
    modal.vm.$emit('update:open', false)
    expect(remove).toHaveBeenCalledExactlyOnceWith('delete-me')
    expect(wrapper.props('open')).toBe(true)
    expect(modal.props('dismissible')).toBe(false)
    expect(wrapper.get('.delete-dialog-confirm').attributes('disabled')).toBeDefined()
    expect(wrapper.findComponent(Button).props('disabled')).toBe(true)
    finish()
    await flushPromises()
    expect(wrapper.props('open')).toBe(false)
  })

  it('keeps the dialog open on failure, hides internal details and permits retry', async () => {
    const remove = vi.fn().mockRejectedValueOnce(new Error('private backend details')).mockResolvedValueOnce(undefined)
    const wrapper = dialog(remove)
    await wrapper.get('.delete-dialog-confirm').trigger('click')
    await flushPromises()
    expect(wrapper.props('open')).toBe(true)
    expect(wrapper.get('[role="alert"]').text()).toBe('Der Chat konnte nicht gelöscht werden. Bitte versuche es erneut.')
    expect(wrapper.text()).not.toContain('private backend details')
    await wrapper.get('.delete-dialog-confirm').trigger('click')
    await flushPromises()
    expect(remove).toHaveBeenCalledTimes(2)
    expect(wrapper.props('open')).toBe(false)
  })

  it('refuses confirmation without a selected conversation', async () => {
    const remove = vi.fn()
    const wrapper = dialog(remove, null)
    await wrapper.get('.delete-dialog-confirm').trigger('click')
    expect(remove).not.toHaveBeenCalled()
  })

  it('uses a safe initial focus and restores an existing trigger or the chat main region', () => {
    const trigger = document.createElement('button')
    document.body.append(trigger)
    const wrapper = dialog(vi.fn(), conversation, trigger)
    const content = wrapper.findComponent(Modal).props('content')
    const event = new Event('focus', { cancelable: true })
    content.onOpenAutoFocus(event)
    expect(event.defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(wrapper.get('.delete-dialog-cancel').element)
    content.onCloseAutoFocus(new Event('focus', { cancelable: true }))
    expect(document.activeElement).toBe(trigger)
    trigger.remove()
    const main = document.createElement('main')
    main.id = 'chat-main'; main.tabIndex = -1
    document.body.append(main)
    content.onCloseAutoFocus(new Event('focus', { cancelable: true }))
    expect(document.activeElement).toBe(main)
  })

  it.each([true, false])('preserves the store contract when deleting an active conversation: %s', async (active) => {
    const chat = createChatState(createMockTransport())
    const remove = chat.conversations.create('Entfernen')
    const keep = chat.conversations.create('Behalten')
    chat.drafts.records.value = { [remove.id]: 'Entwurf entfernen', [keep.id]: 'Entwurf behalten' }
    if (active) chat.conversations.select(remove.id)
    const wrapper = dialog(chat.remove, remove)
    await wrapper.get('.delete-dialog-confirm').trigger('click')
    await flushPromises()
    expect(chat.conversations.visible.value.map(item => item.id)).toEqual([keep.id])
    expect(chat.conversations.activeId.value).toBe(active ? null : keep.id)
    expect(chat.drafts.records.value).toEqual({ [keep.id]: 'Entwurf behalten' })
    expect(wrapper.props('open')).toBe(false)
  })
})
