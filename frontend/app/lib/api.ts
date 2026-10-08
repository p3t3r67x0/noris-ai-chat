import type { ApiPaths } from '../types/generated/api'

export type Readiness = ApiPaths['/api/v1/health/ready']['get']['responses'][200]

export class ApiError extends Error {
  constructor(readonly status: number, readonly requestId: string | null) {
    super('Service request failed')
    this.name = 'ApiError'
  }
}

export async function getReadiness(
  signal: AbortSignal | null = null,
  fetcher: typeof fetch = globalThis.fetch,
): Promise<Readiness> {
  const response = await fetcher('/api/v1/health/ready', {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
    signal,
  })
  if (!response.ok) {
    throw new ApiError(response.status, response.headers.get('X-Request-ID'))
  }
  return await response.json() as Readiness
}
