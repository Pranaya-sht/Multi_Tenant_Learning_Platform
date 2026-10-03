const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/+$/, '')

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function apiRequest(path, { method = 'GET', token, body, signal } = {}) {
  let response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      method,
      signal: signal
        ? AbortSignal.any([signal, AbortSignal.timeout(15000)])
        : AbortSignal.timeout(15000),
      headers: {
        Accept: 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new ApiError('Could not reach the server. Check your connection and try again.')
  }
  if (response.status === 204) return null
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = data?.detail
    const message = Array.isArray(detail)
      ? detail.map((item) => `${item.loc.slice(1).join(' ')}: ${item.msg}`).join('. ')
      : typeof detail === 'string'
        ? detail
        : 'The request could not be completed. Please try again.'
    throw new ApiError(message, response.status)
  }
  if (data === null) throw new ApiError('The server returned an unexpected response.')
  return data
}

// Lists are paginated on the backend. Fetch only the currently opened collection.
export async function fetchCollection(request, path, signal) {
  const rows = []
  for (let offset = 0; ; offset += 100) {
    const page = await request(`${path}?limit=100&offset=${offset}`, { signal })
    rows.push(...page)
    if (page.length < 100) return rows
  }
}

export async function getHealth({ signal } = {}) {
  const response = await fetch(`${apiBaseUrl}/health/live`, {
    signal,
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) throw new Error('API is unavailable')
  const body = await response.json()
  if (body.status !== 'ok') throw new Error('Unexpected API health response')
  return body
}
