import { describe, expect, it, vi } from 'vitest'
import { ApiError, getReadiness } from '../../app/lib/api'

describe('API boundary', () => {
  it('uses same-origin credentials and the generated readiness contract', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ status: 'ready' }))
    await expect(getReadiness(null, fetcher)).resolves.toEqual({ status: 'ready' })
    expect(fetcher).toHaveBeenCalledWith('/api/v1/health/ready', {
      credentials: 'same-origin', headers: { Accept: 'application/json' }, signal: null,
    })
  })

  it('preserves request IDs for failed requests without exposing response content', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response('private detail', {
      status: 503, headers: { 'X-Request-ID': 'request-reference' },
    }))
    await expect(getReadiness(null, fetcher)).rejects.toMatchObject({
      name: 'ApiError', status: 503, requestId: 'request-reference',
    })
    await expect(getReadiness(null, fetcher)).rejects.toThrow(ApiError)
  })

  it('passes cancellation to the transport', async () => {
    const controller = new AbortController()
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new DOMException('Aborted', 'AbortError'))
    controller.abort()
    await expect(getReadiness(controller.signal, fetcher)).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetcher.mock.calls[0]?.[1]?.signal).toBe(controller.signal)
  })
})
