const TOKEN_KEY = 'civic_token'
const USER_KEY = 'civic_user'

// Storage wrapper: localStorage can be unavailable in some embedded/preview
// contexts — fall back to in-memory so the app never crashes.
const mem = { token: null, user: null }

function lsGet(key, memKey) {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return mem[memKey] ?? null
  }
}

function lsSet(key, value, memKey) {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    mem[memKey] = value
  }
}

function lsDel(key, memKey) {
  try {
    window.localStorage.removeItem(key)
  } catch {
    delete mem[memKey]
  }
}

export function getToken() {
  return lsGet(TOKEN_KEY, 'token')
}

export function getStoredUser() {
  try {
    const raw = lsGet(USER_KEY, 'user')
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function saveSession(token, user) {
  lsSet(TOKEN_KEY, token, 'token')
  lsSet(USER_KEY, JSON.stringify(user), 'user')
  setCookie(token)
}

export function clearSession() {
  lsDel(TOKEN_KEY, 'token')
  lsDel(USER_KEY, 'user')
  deleteCookie()
}

// Session token channels. The token is sent on ALL THREE of these so that
// whatever a preview proxy decides to strip, at least one channel survives:
//   1. `Authorization: Bearer <t>`  — standard REST
//   2. `X-Civic-Token: <t>`         — custom header proxies don't normally strip
//   3. `civic_token` cookie         — attached automatically by the browser
const COOKIE_NAME = 'civic_token'

function cookieAttrs() {
  // SameSite=None is only accepted with Secure (https). Local http dev falls
  // back to Lax. SameSite=None is what lets the cookie survive when the app
  // is embedded in a cross-site frame (e.g. the Arena preview).
  return window.location.protocol === 'https:'
    ? '; path=/; max-age=43200; SameSite=None; Secure'
    : '; path=/; max-age=43200; SameSite=Lax'
}

function setCookie(token) {
  try {
    document.cookie = `${COOKIE_NAME}=${encodeURIComponent(token)}${cookieAttrs()}`
  } catch {
    /* cookie storage unavailable — header flows still work */
  }
}

function deleteCookie() {
  try {
    document.cookie = `${COOKIE_NAME}=; path=/; max-age=0`
  } catch {
    /* ignore */
  }
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail)
    this.status = status
  }
}

let redirecting = false

function forceLoginRedirect() {
  const path = window.location.pathname
  if (redirecting || path === '/login' || path === '/register') return
  redirecting = true
  window.location.href = `/login?next=${encodeURIComponent(path)}`
}

export async function api(path, { method = 'GET', body, token } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const t = token !== undefined ? token : getToken()
  if (t) {
    headers['Authorization'] = `Bearer ${t}`
    headers['X-Civic-Token'] = t
  }
  const res = await fetch(path, {
    method,
    headers,
    credentials: 'include',
    body: body ? JSON.stringify(body) : undefined
  })
  if (res.status === 204) return null
  let data = null
  try {
    data = await res.json()
  } catch {
    /* no body */
  }
  if (!res.ok) {
    // Session died (token expired/revoked) -> clean logout + redirect,
    // but only if we actually HAD a session: hard-redirecting a visitor who
    // never logged in just creates an annoying login loop.
    if (res.status === 401 && !path.startsWith('/api/auth/') && getToken()) {
      clearSession()
      forceLoginRedirect()
    }
    const detail =
      (data && (data.detail || data.msg)) ||
      (typeof data === 'string' ? data : '') ||
      res.statusText
    throw new ApiError(
      res.status,
      typeof detail === 'string' ? detail : JSON.stringify(detail)
    )
  }
  return data
}

// Same auth channels as api(), but returns a Blob — for server-rendered
// assets (chart PNGs) that an <img> tag cannot request with headers.
export async function apiBlob(path) {
  const headers = {}
  const t = getToken()
  if (t) {
    headers['Authorization'] = `Bearer ${t}`
    headers['X-Civic-Token'] = t
  }
  const res = await fetch(path, { headers, credentials: 'include' })
  if (!res.ok) {
    if (res.status === 401 && getToken()) {
      clearSession()
      forceLoginRedirect()
    }
    let data = null
    try {
      data = await res.json()
    } catch {
      /* not json */
    }
    const detail =
      (data && (data.detail || data.msg)) ||
      (typeof data === 'string' ? data : '') ||
      res.statusText
    throw new ApiError(res.status, typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return await res.blob()
}
