import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ServiceStatus from '../../app/components/ServiceStatus.vue'

describe('service status', () => {
  it('announces pending status and disables duplicate checks', () => {
    const wrapper = mount(ServiceStatus, { props: { status: 'checking' } })
    expect(wrapper.get('[role="status"]').text()).toBe('Verbindung wird geprüft …')
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
  })

  it('allows a keyboard-usable retry after failure', async () => {
    const wrapper = mount(ServiceStatus, { props: { status: 'unavailable' } })
    expect(wrapper.get('[role="status"]').text()).toBe('Dienst derzeit nicht erreichbar')
    expect(wrapper.get('button').attributes('type')).toBe('button')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('shows service availability', () => {
    const wrapper = mount(ServiceStatus, { props: { status: 'healthy' } })
    expect(wrapper.get('[role="status"]').text()).toBe('Dienst verfügbar')
  })
})
