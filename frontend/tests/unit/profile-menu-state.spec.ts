import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import ProfileMenu from '../../app/components/chat/ProfileMenu.vue'

const Dropdown = defineComponent({
  props: ['open', 'items', 'content'], emits: ['update:open'],
  setup: (props, { slots, emit }) => () => h('div', [
    h('div', { onClick: () => emit('update:open', !props.open) }, slots.default?.()),
    props.open ? h('section', { role: 'menu' }, [slots['content-top']?.({ sub: false })]) : null,
  ]),
})
const Button = defineComponent({ setup: (_, { attrs, slots }) => () => h('button', attrs, slots.default?.()) })
const wrappers: ReturnType<typeof mount>[] = []
afterEach(() => { wrappers.splice(0).forEach(wrapper => wrapper.unmount()); vi.unstubAllGlobals() })

function menu(mobile: boolean, demo = true) {
  const listeners: (() => void)[] = []
  const remove = vi.fn()
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: mobile, addEventListener: (_: string, callback: () => void) => listeners.push(callback), removeEventListener: remove })))
  const wrapper = mount(ProfileMenu, { props: { demo }, global: { stubs: { UDropdownMenu: Dropdown, UButton: Button, UAvatar: true } } })
  wrappers.push(wrapper)
  return { wrapper, dropdown: wrapper.findComponent(Dropdown), listeners, remove }
}

describe('profile menu capability and responsive state', () => {
  it('shows a truthful single-owner identity and only supported actions', async () => {
    const { wrapper, dropdown } = menu(false, false)
    await wrapper.find('button').trigger('click')
    expect(wrapper.text()).toContain('Noris AI')
    expect(wrapper.text()).toContain('Single-Owner-Modus')
    const groups = dropdown.props('items')
    expect(groups.flat().map((item: { label: string }) => item.label)).toEqual(['Einstellungen', 'Hilfe'])
    expect(groups[0][0].to).toBe('/settings/general')
    expect(groups[1][0].children.map((item: { label: string }) => item.label)).toEqual(['Dokumentation', 'Tastaturkürzel', 'Fehler melden'])
    expect(groups[1][0].content).toMatchObject({ side: 'right', collisionPadding: 8, avoidCollisions: true })
  })

  it('uses the same help destinations on touch and resets the nested view when closed', async () => {
    const { wrapper, dropdown } = menu(true)
    await wrapper.find('button').trigger('click')
    const event = new Event('select', { cancelable: true })
    dropdown.props('items')[1][0].onSelect(event)
    await wrapper.vm.$nextTick()
    expect(event.defaultPrevented).toBe(true)
    expect(dropdown.props('items').flat().map((item: { label: string }) => item.label)).toEqual(['Zurück', 'Dokumentation', 'Tastaturkürzel', 'Fehler melden'])
    dropdown.props('items')[0][0].onSelect(new Event('select', { cancelable: true }))
    await wrapper.vm.$nextTick()
    expect(dropdown.props('items')[1][0].label).toBe('Hilfe')
    dropdown.props('items')[1][0].onSelect(event)
    dropdown.vm.$emit('update:open', false)
    await wrapper.vm.$nextTick()
    expect(dropdown.props('open')).toBe(false)
    expect(dropdown.props('items')[0][0].label).toBe('Einstellungen')
  })

  it('closes on Tab or a breakpoint change and removes media listeners', async () => {
    const { wrapper, dropdown, listeners, remove } = menu(false)
    for (const shiftKey of [false, true]) {
      await wrapper.find('button').trigger('click')
      const event = new KeyboardEvent('keydown', { key: 'Tab', shiftKey, cancelable: true })
      wrapper.find('section').element.dispatchEvent(event)
      await wrapper.vm.$nextTick()
      expect(event.defaultPrevented).toBe(true)
      expect(dropdown.props('open')).toBe(false)
    }
    await wrapper.find('button').trigger('click')
    listeners[1]!()
    await wrapper.vm.$nextTick()
    expect(dropdown.props('open')).toBe(false)
    wrapper.unmount()
    expect(remove).toHaveBeenCalledTimes(2)
  })
})
