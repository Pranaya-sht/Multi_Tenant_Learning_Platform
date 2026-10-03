import { useCallback, useEffect, useState } from 'react'
import { fetchCollection } from '../lib/api.js'
import { useAuth } from '../state/context.js'

export function useResource(path, collection = false) {
  const { request } = useAuth()
  const [version, setVersion] = useState(0)
  const [state, setState] = useState({ data: null, loading: Boolean(path), error: null })
  const key = `${path}:${collection}:${version}`
  const refresh = useCallback(() => setVersion((value) => value + 1), [])
  useEffect(() => {
    if (!path) return
    const controller = new AbortController()
    const pending = collection
      ? fetchCollection(request, path, controller.signal)
      : request(path, { signal: controller.signal })
    pending.then(
      (data) => {
        if (!controller.signal.aborted) setState({ key, data, loading: false, error: null })
      },
      (error) => {
        if (!controller.signal.aborted) setState({ key, data: null, loading: false, error })
      },
    )
    return () => controller.abort()
  }, [path, collection, request, key])
  return {
    ...(state.key === key ? state : { data: null, loading: Boolean(path), error: null }),
    refresh,
  }
}
