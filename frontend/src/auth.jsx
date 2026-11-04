import { createContext, useContext, useEffect, useState } from 'react'
import { api, getToken, getStoredUser, saveSession, clearSession } from './api.js'
import { supabase, isDemoEmail } from './supabase.js'

/*
 * Session model:
 *  - REAL users: authenticate against Supabase Auth (supabase.auth.*).
 *    The Supabase access token is sent on the app's normal API channels
 *    (Authorization / X-Civic-Token / cookie); the backend validates it
 *    against Supabase and maps it to a local account (created on first
 *    login, keeping role & team by email).
 *  - DEMO accounts (seeded civic.demo users): local JWTs via /api/auth/*.
 *    They power the seeded demo data and keep working offline of Supabase.
 */

const AuthCtx = createContext(null)

function friendlyAuthError(error) {
  const m = (error?.message || 'Authentication failed').toLowerCase()
  if (m.includes('invalid login credentials')) return 'Invalid email or password.'
  if (m.includes('email not confirmed'))
    return 'Please confirm your email first — check your inbox for the verification link.'
  if (m.includes('registered'))
    return 'An account with this email already exists — try logging in instead.'
  if (m.includes('password should be at least') || m.includes('password must be at least'))
    return 'Password is too short — use at least 6 characters.'
  if (m.includes('rate limit') || m.includes('too many'))
    return 'Too many attempts — wait a minute and try again.'
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

  // Boot: an existing Supabase session (survives page reloads) wins over a
  // stale local demo token.
  useEffect(() => {
    let cancelled = false
    async function boot() {
      let token = null
      try {
        const { data } = await supabase.auth.getSession()
        if (data?.session?.access_token) token = data.session.access_token
      } catch {
        /* storage unavailable */
      }
      if (!token) token = getToken() || cookieToken()
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

  // Track Supabase session changes (token refresh, sign-out from another tab).
  // NOTE: supabase-js emits INITIAL_SESSION on subscribe — for a visitor who
  // is NOT signed in to Supabase that session is null. We must NOT treat it
  // as a sign-out, or it would wipe a valid local/demo session on every load.
  useEffect(() => {
    const { data: sub } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'SIGNED_IN' || event === 'TOKEN_REFRESHED') {
        if (session?.access_token) {
          saveSession(session.access_token, getStoredUser())
          api('/api/auth/me', { token: session.access_token })
            .then((me) => {
              saveSession(session.access_token, me)
              setUser(me)
            })
            .catch(() => {
              /* transient — next boot will re-resolve */
            })
        }
      } else if (event === 'SIGNED_OUT') {
        clearSession()
        setUser(null)
      }
      // INITIAL_SESSION is intentionally ignored (boot() owns that).
    })
    return () => sub.subscription.unsubscribe()
  }, [])

  async function login(email, password) {
    const em = (email || '').trim().toLowerCase()
    if (!isDemoEmail(em)) {
      // 1) Real Supabase account
      const { data, error } = await supabase.auth.signInWithPassword({ email: em, password })
      if (error) throw new Error(friendlyAuthError(error))
      const me = await meForToken(data.session.access_token)
      saveSession(data.session.access_token, me)
      setUser(me)
      return me
    }
    // 2) Demo account → local database (seeded demo users)
    return localLogin(em, password)
  }

  async function localLogin(email, password) {
    const data = await api('/api/auth/login', { method: 'POST', body: { email, password } })
    saveSession(data.access_token, data.user)
    setUser(data.user)
    return data.user
  }

  async function register(payload) {
    const em = (payload.email || '').trim().toLowerCase()
    const { data, error } = await supabase.auth.signUp({
      email: em,
      password: payload.password,
      data: { name: (payload.name || '').trim(), role: payload.role || 'citizen' },
    })
    if (error) throw new Error(friendlyAuthError(error))
    if (data.session) {
      // Email confirmation is disabled on the project — straight into the app.
      const me = await meForToken(data.session.access_token)
      saveSession(data.session.access_token, me)
      setUser(me)
      return me
    }
    return { needsConfirmation: true }
  }

  async function logout() {
    try {
      await supabase.auth.signOut()
    } catch {
      /* not signed in via Supabase */
    }
    try {
      await api('/api/auth/logout', { method: 'POST' })
    } catch {
      /* token may already be invalid */
    }
    clearSession()
    setUser(null)
  }

  return (
    <AuthCtx.Provider value={{ user, loading, login, localLogin, register, logout }}>
      {children}
    </AuthCtx.Provider>
  )
}

export function useAuth() {
  return useContext(AuthCtx)
}
