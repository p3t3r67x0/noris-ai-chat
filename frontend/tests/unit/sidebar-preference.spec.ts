import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { SIDEBAR_STORAGE_KEY, useSidebarPreference } from '../../app/composables/useSidebarPreference'

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear() })
function preference(desktop: boolean) {
  vi.stubGlobal('matchMedia', () => ({ matches: desktop }))
  return mount(defineComponent({ setup() { return useSidebarPreference() }, render() { return h('button', { onClick: () => { this.sidebarOpen = !this.sidebarOpen } }, String(this.sidebarOpen)) } }))
}
describe('desktop sidebar preference', () => {
  it('restores the desktop choice after mount and stores later changes', async () => {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, 'false')
    const wrapper = preference(true)
    await nextTick()
    expect(wrapper.text()).toBe('false')
    await wrapper.get('button').trigger('click')
    expect(localStorage.getItem(SIDEBAR_STORAGE_KEY)).toBe('true')
    wrapper.unmount()
  })
  it('does not overwrite the desktop choice when a mobile drawer changes', async () => {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, 'true')
    const wrapper = preference(false)
    await wrapper.get('button').trigger('click')
    expect(localStorage.getItem(SIDEBAR_STORAGE_KEY)).toBe('true')
    wrapper.unmount()
  })
  it('keeps navigation usable if storage is unavailable', async () => {
    const get = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('Blocked') })
    const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Blocked') })
    const wrapper = preference(true)
    await wrapper.get('button').trigger('click')
    expect(wrapper.text()).toBe('false')
    wrapper.unmount(); get.mockRestore(); set.mockRestore()
  })
})
