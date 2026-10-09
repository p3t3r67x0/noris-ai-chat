import { defineComponent } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
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

describe('Dynamic model permissions', () => {
  beforeEach(() => { localStorage.clear() })
  const alpha = { id: 'alpha', name: 'Alpha', available: true, streaming: true }
  const beta = { id: 'beta', name: 'Beta', available: true, streaming: true }
  function mountCatalog(fetcher: typeof fetch) {
    return mount(defineComponent({ setup: () => useModelSelection({ mode: 'real', fetcher }), template: '<div>{{ modelId }} {{ notice }} {{ error }}</div>' }))
  }

  it('preserves a revoked preference and requires an explicit fallback selection', async () => {
    localStorage.setItem('noris-ai:model', 'alpha')
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(Response.json({ models: [alpha, beta], default_model: 'alpha', limits: DEFAULT_CHAT_LIMITS })).mockResolvedValueOnce(Response.json({ models: [beta], default_model: 'beta', limits: DEFAULT_CHAT_LIMITS }))
    const wrapper = mountCatalog(fetcher)
    await flushPromises()
    expect(wrapper.vm.canSend).toBe(true)
    await wrapper.vm.refresh()
    expect(wrapper.vm.modelId).toBe('alpha')
    expect(wrapper.vm.canSend).toBe(false)
    expect(wrapper.text()).toContain('nicht mehr verfügbar')
    expect(localStorage.getItem('noris-ai:model')).toBe('alpha')
    wrapper.vm.chooseFallback()
    await flushPromises()
    expect(wrapper.vm.modelId).toBe('beta')
    expect(wrapper.vm.canSend).toBe(true)
    expect(fetcher).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('accepts empty catalogs without fictional defaults', async () => {
    const wrapper = mountCatalog(async () => Response.json({ models: [], default_model: null, limits: DEFAULT_CHAT_LIMITS }))
    await flushPromises()
    expect(wrapper.vm.error).toBeNull()
    expect(wrapper.vm.canSend).toBe(false)
    expect(wrapper.text()).toContain('keine Chatmodelle')
    expect(CHAT_MODELS).toEqual([])
    wrapper.unmount()
  })

  it('marks stale metadata clearly and blocks generation', async () => {
    const wrapper = mountCatalog(async () => Response.json({ models: [{ ...alpha, available: false }], default_model: null, status: 'stale', limits: DEFAULT_CHAT_LIMITS }))
    await flushPromises()
    expect(wrapper.vm.stale).toBe(true)
    expect(wrapper.vm.canSend).toBe(false)
    expect(CHAT_MODELS[0]?.disabled).toBe(true)
    expect(wrapper.text()).toContain('veraltet')
    wrapper.unmount()
  })

  it('coalesces concurrent refreshes and never substitutes a failed catalog', async () => {
    let resolve: (response: Response) => void = () => {}
    const fetcher = vi.fn<typeof fetch>().mockImplementation(() => new Promise<Response>((done) => { resolve = done }))
    const wrapper = mountCatalog(fetcher)
    const first = wrapper.vm.refresh()
    const second = wrapper.vm.refresh()
    expect(fetcher).toHaveBeenCalledTimes(1)
    resolve(new Response('', { status: 503 }))
    await Promise.all([first, second])
    expect(wrapper.vm.canSend).toBe(false)
    expect(CHAT_MODELS).toEqual([])
    wrapper.unmount()
  })
})
