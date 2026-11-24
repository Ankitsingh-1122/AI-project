import { createContext, useContext, useEffect, useState } from 'react'
import { api, getToken, getStoredUser, saveSession, clearSession } from './api.js'

/*
 * Session model:
 * Native local backend API (/api/auth/*) with SQLite/SQLAlchemy.
 * Supports registration, demo accounts, and custom logins reliably offline with 0 delay.
 */

const AuthCtx = createContext(null)

function friendlyAuthError(error) {
  const m = (error?.message || 'Authentication failed').toLowerCase()
  if (m.includes('invalid email or password') || m.includes('invalid login credentials') || m.includes('401')) {
    return 'Invalid email or password.'
  }
  if (m.includes('registered') || m.includes('already exists') || m.includes('409')) {
    return 'An account with this email already exists — try logging in instead.'
  }
  if (m.includes('password should be at least') || m.includes('password must be at least') || (m.includes('password') && m.includes('short'))) {
    return 'Password is too short — use at least 6 characters.'
  }
  if (m.includes('rate limit') || m.includes('too many')) {
    return 'Too many attempts — wait a minute and try again.'
  }
  return error?.message || 'Authentication failed'
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  function meForToken(token) {
    return api('/api/auth/me', { token })
  }

  // The token may live ONLY in the civic_token cookie (e.g. localStorage is
  // blocked in some embedded/preview contexts) — read it as a last channel.
  function cookieToken() {
    try {
      const row = document.cookie.split('; ').find((r) => r.startsWith('civic_token='))
      return row ? decodeURIComponent(row.slice('civic_token='.length)) : null
    } catch {
      return null
    }
  }

  // Boot: resolve existing session on app load
  useEffect(() => {
    let cancelled = false
    async function boot() {
      const token = getToken() || cookieToken()
      if (!token) {
        if (!cancelled) setLoading(false)
        return
      }
      try {
        const me = await meForToken(token)
        if (cancelled) return
        saveSession(token, me)
        setUser(me)
      } catch {
        if (cancelled) return
        clearSession()
        setUser(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    boot()
    return () => {
      cancelled = true
    }
  }, [])

  async function login(email, password) {
    const em = (email || '').trim().toLowerCase()
    try {
      const data = await api('/api/auth/login', {
        method: 'POST',
        body: { email: em, password },
      })
      saveSession(data.access_token, data.user)
      setUser(data.user)
      return data.user
    } catch (err) {
      throw new Error(friendlyAuthError(err))
    }
  }

  async function register(payload) {
    const em = (payload.email || '').trim().toLowerCase()
    const name = (payload.name || '').trim()
    try {
      const data = await api('/api/auth/register', {
        method: 'POST',
        body: {
          name,
          email: em,
          password: payload.password,
          role: payload.role || 'citizen',
        },
      })
      saveSession(data.access_token, data.user)
      setUser(data.user)
      return data.user
    } catch (err) {
      throw new Error(friendlyAuthError(err))
    }
  }

  async function logout() {
    try {
      await api('/api/auth/logout', { method: 'POST' })
    } catch {
      /* token may already be invalid */
    }
    clearSession()
    setUser(null)
  }

  return (
    <AuthCtx.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthCtx.Provider>
  )
}

export function useAuth() {
  return useContext(AuthCtx)
}
