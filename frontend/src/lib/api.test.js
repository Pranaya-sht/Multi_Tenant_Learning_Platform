import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiRequest, fetchCollection, getHealth } from './api.js'

afterEach(() => vi.unstubAllGlobals())

describe('API health connection', () => {
  it('uses the versioned API and preserves the abort signal', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'ok' })))
    vi.stubGlobal('fetch', fetch)
    const controller = new AbortController()
    await expect(getHealth({ signal: controller.signal })).resolves.toEqual({ status: 'ok' })
    expect(fetch).toHaveBeenCalledWith('/api/v1/health/live', {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })
  })

  it('rejects unsuccessful HTTP responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 503 })))
    await expect(getHealth()).rejects.toThrow('API is unavailable')
  })

  it('rejects an unexpected response instead of displaying a connected state', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'error' }))),
    )
    await expect(getHealth()).rejects.toThrow('Unexpected API health response')
  })

  it('propagates network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(getHealth()).rejects.toThrow('Failed to fetch')
  })
})

describe('authenticated API requests', () => {
  it('sends the tenant login scope without an authorization header', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ access_token: 'signed-token' })))
    vi.stubGlobal('fetch', fetch)
    const body = {
      email: 'learner@example.com',
      password: 'test-only-password',
      tenant_slug: 'institute-a',
    }
    await apiRequest('/auth/login', { method: 'POST', body })
    expect(fetch.mock.calls[0][1].headers.Authorization).toBeUndefined()
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(body)
  })
  it('uses the bearer token and handles an empty successful mutation response', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetch)
    await expect(apiRequest('/auth/logout', { token: 'token', method: 'POST' })).resolves.toBeNull()
    expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer token')
  })
  it('preserves credential errors separately from forbidden access', async () => {
    for (const status of [401, 403]) {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Denied' }), { status })),
      )
      await expect(apiRequest('/tenant/courses')).rejects.toMatchObject({
        status,
        message: 'Denied',
      })
    }
  })
  it('turns validation details into readable field errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ detail: [{ loc: ['body', 'email'], msg: 'Invalid email address' }] }),
            { status: 422 },
          ),
        ),
    )
    await expect(apiRequest('/tenant/users')).rejects.toThrow('email: Invalid email address')
  })
  it('normalizes network failures without displaying false success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Network failure')))
    await expect(apiRequest('/tenant')).rejects.toThrow('Could not reach the server')
  })
  it('propagates cancellation to the underlying request', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 'course' })))
    vi.stubGlobal('fetch', fetch)
    const controller = new AbortController()
    await apiRequest('/tenant', { signal: controller.signal })
    controller.abort()
    expect(fetch.mock.calls[0][1].signal.aborted).toBe(true)
  })
  it('fetches all backend pages instead of silently truncating a collection', async () => {
    const request = vi
      .fn()
      .mockResolvedValueOnce(Array.from({ length: 100 }, (_, id) => ({ id })))
      .mockResolvedValueOnce([{ id: 100 }])
    const rows = await fetchCollection(request, '/tenant/courses')
    expect(rows).toHaveLength(101)
    expect(request.mock.calls.map(([url]) => url)).toEqual([
      '/tenant/courses?limit=100&offset=0',
      '/tenant/courses?limit=100&offset=100',
    ])
  })
})
