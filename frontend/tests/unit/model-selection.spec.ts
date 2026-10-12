import { defineComponent } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CHAT_MODELS, useModelSelection } from '../../app/composables/useModelSelection'
import { DEFAULT_CHAT_LIMITS } from '../../app/lib/chat/limits'

describe('Configured model catalog', () => {
  it('requires both provider image modality and vision capability without changing the selected model', async () => {
    localStorage.clear()
    const wrapper = mount(defineComponent({ setup: () => useModelSelection({ mode: 'real', fetcher: async () => Response.json({ models: [
      { id: 'text', name: 'Text', available: true, streaming: true, vision: false, input_modalities: ['text'] },
      { id: 'image', name: 'Image', available: true, streaming: true, vision: true, input_modalities: ['text', 'image'] },
      { id: 'unconfirmed', name: 'Unconfirmed', available: true, streaming: true, vision: true, input_modalities: ['text'] },
      { id: 'image-only', name: 'Image only', available: true, streaming: true, vision: true, input_modalities: ['image'] },
    ], default_model: 'text', limits: DEFAULT_CHAT_LIMITS }) }), template: '<div />' }))
    await flushPromises()
    expect(CHAT_MODELS.map(model => model.imageInput)).toEqual([false, true, false, false])
    expect(wrapper.vm.modelId).toBe('text')
    wrapper.unmount()
  })
  it('exposes provider limits and unavailable models without changing composer permissions', async () => {
    const wrapper = mount(defineComponent({ setup: () => useModelSelection({ mode: 'real', fetcher: async () => Response.json({ models: [
      { id: 'alpha', name: 'Alpha', description: 'Provider description', available: true, streaming: true, provider_context_window: 131072, effective_max_output_tokens: 8192 },
      { id: 'offline', name: 'Offline', available: false, streaming: true },
    ], default_model: 'alpha', limits: DEFAULT_CHAT_LIMITS }) }), template: '<div />' }))
    await flushPromises()
    expect(CHAT_MODELS.map(model => model.id)).toEqual(['alpha'])
    expect(wrapper.vm.catalogModels[0]).toMatchObject({ contextWindow: 131072, effectiveOutputLimit: 8192, providerDescription: 'Provider description', disabled: false })
    expect(wrapper.vm.catalogModels[1]).toMatchObject({ id: 'offline', disabled: true })
    expect(wrapper.vm.catalogModels[1]?.effectiveOutputLimit).toBeUndefined()
    wrapper.unmount()
  })
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

describe('reasoning catalog freshness', () => {
  it('uses only explicit server preferences and replaces revoked or stale capabilities', async () => {
    localStorage.clear()
    const models = [
      { id: 'gpt', name: 'GPT-OSS 120B', available: true, streaming: true, reasoning: true, reasoning_preferences: ['instant', 'medium', 'high', 'unknown'] },
      { id: 'glm', name: 'GLM 5.2', available: true, streaming: true, reasoning: true, reasoning_preferences: ['high', 'very_high'] },
      { id: 'unconfirmed', name: 'Reasoning Max Pro', available: true, streaming: true, reasoning: true, reasoning_efforts: ['low', 'medium', 'high', 'max'] },
      { id: 'contradictory', name: 'No reasoning', available: true, streaming: true, reasoning: false, reasoning_preferences: ['high'] },
    ]
    const catalog = (values: Record<string, unknown>[], status = 'fresh') => Response.json({ models: values, default_model: 'gpt', limits: DEFAULT_CHAT_LIMITS, status })
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(catalog(models)).mockResolvedValueOnce(catalog(models.map(model => ({ ...model, reasoning_preferences: [] })))).mockResolvedValueOnce(catalog(models, 'stale'))
    const wrapper = mount(defineComponent({ setup: () => useModelSelection({ mode: 'real', fetcher }), template: '<div />' }))
    await flushPromises()
    expect(CHAT_MODELS.map(model => model.reasoningPreferences)).toEqual([['instant', 'medium', 'high'], ['high', 'very_high'], [], []])
    await wrapper.vm.refresh()
    expect(CHAT_MODELS.every(model => model.reasoningPreferences?.length === 0)).toBe(true)
    await wrapper.vm.refresh()
    expect(CHAT_MODELS.every(model => model.disabled && model.reasoningPreferences?.length === 0)).toBe(true)
    wrapper.unmount()
  })
})
