import { useCallback, useEffect, useState } from 'react'
import { apiRequest } from '../lib/api.js'
import { AuthContext } from './context.js'

const STORAGE_KEY = 'synapse.access-token'
function storedToken() {
  try {
    return sessionStorage.getItem(STORAGE_KEY) || ''
  } catch {
    return ''
  }
}
function saveToken(value) {
  try {
    if (value) sessionStorage.setItem(STORAGE_KEY, value)
    else sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    /* Private browsing can disable storage; in-memory sign-in still works. */
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(storedToken)
  const [user, setUser] = useState(null)
  const [restoring, setRestoring] = useState(Boolean(token))
  const [restoreError, setRestoreError] = useState(null)
  const [notice, setNotice] = useState('')
  const [expired, setExpired] = useState(false)
  const [retry, setRetry] = useState(0)
  const clear = useCallback((message = '') => {
    saveToken('')
    setToken('')
    setUser(null)
    setExpired(false)
    setNotice(message)
    setRestoreError(null)
    setRestoring(false)
    window.location.hash = '/overview'
  }, [])

  useEffect(() => {
    if (!token) return
    const controller = new AbortController()
    apiRequest('/auth/me', { token, signal: controller.signal }).then(
      (identity) => {
        if (!controller.signal.aborted) {
          setUser(identity)
          setRestoring(false)
        }
      },
      (error) => {
        if (controller.signal.aborted) return
        if (error.status === 401) clear('Your session ended. Please sign in again.')
        else {
          setRestoreError(error)
          setRestoring(false)
        }
      },
    )
    return () => controller.abort()
  }, [token, clear, retry])

  const request = useCallback(
    async (path, options = {}) => {
      try {
        const result = await apiRequest(path, { ...options, token })
        if (path === '/tenant') setExpired(result.status === 'expired')
        return result
      } catch (error) {
        if (error.status === 401) clear('Your session ended. Please sign in again.')
        if (error.status === 403 && error.message.includes('Tenant trial expired')) setExpired(true)
        throw error
      }
    },
    [token, clear],
  )

  async function login(body) {
    const result = await apiRequest('/auth/login', { method: 'POST', body })
    saveToken(result.access_token)
    setNotice('')
    setUser(result.user)
    setExpired(false)
    setRestoring(true)
    window.location.hash = '/overview'
    setToken(result.access_token)
  }

  async function logout() {
    let message = 'You have signed out.'
    try {
      await request('/auth/logout', { method: 'POST' })
    } catch {
      message = 'Signed out on this device. The server could not confirm token revocation.'
    }
    clear(message)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        request,
        login,
        logout,
        restoring,
        restoreError,
        retryRestore: () => {
          setRestoring(true)
          setRestoreError(null)
          setRetry((value) => value + 1)
        },
        clear,
        notice,
        expired,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
