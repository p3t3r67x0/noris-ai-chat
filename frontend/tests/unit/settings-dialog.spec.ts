import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import SettingsDialog from '../../app/components/settings/SettingsDialog.vue'

const Modal = defineComponent({
  props: ['open', 'title', 'dismissible', 'close'], emits: ['update:open'],
  setup: (props, { slots }) => () => props.open ? h('section', { 'aria-label': props.title }, [slots.body?.(), slots.footer?.()]) : null,
})
const Tabs = defineComponent({ setup: (_, { slots }) => () => h('div', [slots.general?.(), slots['data-controls']?.()]) })
const Button = defineComponent({
  props: ['label', 'disabled', 'loading'],
  setup: (props, { attrs }) => () => h('button', { ...attrs, disabled: props.disabled }, props.label),
})
const wrappers: ReturnType<typeof mount>[] = []
afterEach(() => wrappers.splice(0).forEach(wrapper => wrapper.unmount()))
function settings(importLocalChats = vi.fn(async () => {}), importAvailable = true, importReady = true) {
  const wrapper = mount(SettingsDialog, {
    props: { open: true, importAvailable, importReady, importBusy: false, importLocalChats, importFeedback: null },
    global: { stubs: { UModal: Modal, UTabs: Tabs, UButton: Button, UColorModeSelect: true } },
  })
  wrappers.push(wrapper)
  return wrapper
}
function button(wrapper: ReturnType<typeof settings>, label: string) {
  return wrapper.findAll('button').find(element => element.text() === label)!
}

describe('settings data controls', () => {
  it('hides importing when the current transport has no import capability or no local snapshot', () => {
    const wrapper = settings(undefined, false)
    expect(wrapper.text()).not.toContain('Lokale Chats importieren')
    expect(wrapper.findAll('button')).toHaveLength(0)
  })

  it('requires explicit confirmation and cancels without calling the existing import process', async () => {
    const run = vi.fn(async () => {})
    const wrapper = settings(run)
    expect(wrapper.text()).toContain('Übertrage bisher lokal gespeicherte Unterhaltungen in die PostgreSQL-Datenbank.')
    await button(wrapper, 'Importieren').trigger('click')
    expect(run).not.toHaveBeenCalled()
    await button(wrapper, 'Abbrechen').trigger('click')
    expect(run).not.toHaveBeenCalled()
    expect(button(wrapper, 'Import ausdrücklich starten')).toBeUndefined()
  })

  it('calls the existing import once and blocks duplicate confirmation and dismissal while pending', async () => {
    let finish!: () => void
    const run = vi.fn(() => new Promise<void>(resolve => { finish = resolve }))
    const wrapper = settings(run)
    await button(wrapper, 'Importieren').trigger('click')
    const confirm = button(wrapper, 'Import ausdrücklich starten')
    await Promise.all([confirm.trigger('click'), confirm.trigger('click')])
    expect(run).toHaveBeenCalledOnce()
    for (const modal of wrapper.findAllComponents(Modal)) {
      expect(modal.props('dismissible')).toBe(false)
      expect(modal.props('close')).toBe(false)
      modal.vm.$emit('update:open', false)
    }
    expect(wrapper.emitted('update:open')).toBeUndefined()
    expect(button(wrapper, 'Abbrechen').attributes('disabled')).toBeDefined()
    finish(); await flushPromises()
    expect(button(wrapper, 'Import ausdrücklich starten')).toBeUndefined()
    expect(wrapper.findAllComponents(Modal)[0]!.props('dismissible')).toBe(true)
    await wrapper.setProps({ importFeedback: '1 Chats importiert, 0 bereits vorhanden. Die lokale Sicherung bleibt erhalten.' })
    expect(wrapper.get('[role="status"]').text()).toContain('1 Chats importiert')
  })

  it('disables importing until the backend is ready', () => {
    expect(button(settings(undefined, true, false), 'Importieren').attributes('disabled')).toBeDefined()
  })
})
