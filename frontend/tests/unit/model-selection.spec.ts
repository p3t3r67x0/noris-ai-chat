import { defineComponent } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { CHAT_MODELS, useModelSelection } from '../../app/composables/useModelSelection'
import { DEFAULT_CHAT_LIMITS } from '../../app/lib/chat/limits'

describe('Configured model catalog', () => {
  it('reuses the existing reactive model list and restores only configured IDs', async () => {
    const identity = CHAT_MODELS
    localStorage.setItem('noris-ai:model', 'fixture-beta')
    const component = defineComponent({ setup: () => useModelSelection({ mode: 'real', fetcher: async () => Response.json({ models: [{ id: 'fixture-alpha', name: 'Alpha', available: true, streaming: true }, { id: 'fixture-beta', name: 'Beta', available: true, streaming: true }, { id: 'offline', name: 'Offline', available: false, streaming: true }], default_model: 'fixture-alpha', limits: DEFAULT_CHAT_LIMITS }) }), template: '<div>{{ modelId }}</div>' })
    const wrapper = mount(component)
    await flushPromises()
    expect(CHAT_MODELS).toBe(identity)
    expect(CHAT_MODELS.map(model => model.id)).toEqual(['fixture-alpha', 'fixture-beta'])
    expect(wrapper.text()).toBe('fixture-beta')
    wrapper.unmount()
  })

  it('does not fall back to fictional mock models when Real catalog fails', async () => {
    const wrapper = mount(defineComponent({ setup: () => useModelSelection({ mode: 'real', fetcher: async () => new Response('unauthorized', { status: 401 }) }), template: '<div>{{ error }}</div>' }))
    await flushPromises()
    expect(CHAT_MODELS).toEqual([])
    expect(wrapper.text()).toContain('melde dich')
    wrapper.unmount()
  })

  it('keeps credential-free Mock development available', async () => {
    const wrapper = mount(defineComponent({ setup: () => useModelSelection(), template: '<div>{{ modelId }}</div>' }))
    await flushPromises()
    expect(CHAT_MODELS.map(model => model.id)).toEqual(['balanced', 'reasoning', 'fast'])
    expect(wrapper.text()).toBe('balanced')
    wrapper.unmount()
  })
})
