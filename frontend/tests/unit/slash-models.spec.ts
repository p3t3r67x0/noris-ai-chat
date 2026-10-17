import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { computed, defineComponent, h, nextTick, ref } from 'vue'
import { useSlashCommands } from '../../app/composables/useSlashCommands'
import type { SlashChoice } from '../../app/composables/useSlashCommands'
import type { CommandContext } from '../../app/lib/chat/commands'

function setup() {
  const text = ref('Mein Entwurf /modell')
  const busy = ref(false)
  const catalog = ref<SlashChoice[]>([
    { id: 'one', label: 'Model one', description: 'Available', checked: true },
    { id: 'two', label: 'Model two', description: 'Unavailable', disabled: true },
  ])
  const select = vi.fn()
  const input = document.createElement('textarea')
  input.value = text.value
  input.setSelectionRange(text.value.length, text.value.length)
  let state!: ReturnType<typeof useSlashCommands>
  const wrapper = mount(defineComponent({ setup() {
    const context = computed<CommandContext>(() => ({ learning: false, search: false, reasoning: false, model: !busy.value, image: false, file: false, actions: { model: () => { void nextTick(state.showModels) } } }))
    state = useSlashCommands(text, context, () => input, () => null, { items: catalog, available: () => !busy.value, select })
    return () => h('div')
  } }))
  return { text, busy, catalog, select, input, state, wrapper }
}

describe('model selection inside the existing command menu', () => {
  it('preserves the remaining draft and keeps submit local throughout the submenu', async () => {
    const { state, text, select, wrapper } = setup()
    state.update()
    expect(state.guardSubmit()).toBe(true)
    await nextTick()
    expect(text.value).toBe('Mein Entwurf ')
    expect(state.modelView.value).toBe(true)
    expect(state.open.value).toBe(true)
    expect(state.guardSubmit()).toBe(true)
    expect(select).toHaveBeenCalledWith('one')
    expect(state.open.value).toBe(false)
    expect(text.value).toBe('Mein Entwurf ')
    wrapper.unmount()
  })
  it('rechecks disabled models, revoked catalog entries and streaming guards at selection time', () => {
    const { state, busy, catalog, select, wrapper } = setup()
    state.showModels()
    state.chooseModel(catalog.value[1]!)
    expect(select).not.toHaveBeenCalled()
    const previous = catalog.value[0]!
    catalog.value = catalog.value.slice(1)
    state.chooseModel(previous)
    expect(select).not.toHaveBeenCalled()
    catalog.value = [previous]
    busy.value = true
    state.chooseModel(previous)
    expect(select).not.toHaveBeenCalled()
    expect(state.unavailable.value).toBe(true)
    busy.value = false
    state.chooseModel(previous)
    expect(select).toHaveBeenCalledWith('one')
    wrapper.unmount()
  })
})
