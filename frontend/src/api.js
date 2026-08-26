// One place that talks to the backend, so the token is attached in exactly one
// place and nothing else has to remember to do it.
//
// The token lives in localStorage. That is the pragmatic choice for a demo: the
// page survives a refresh, which matters when you are presenting. A production
// system would prefer an httpOnly cookie, because JavaScript cannot read one and
// therefore neither can a script injected into the page.

const TOKEN_KEY = 'aiia.token'
const USER_KEY = 'aiia.user'

export function savedToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function savedUser() {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function saveSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

// Thrown for any non-2xx answer. `status` is kept so callers can tell "your
// token is dead" (401) from "you are not allowed" (403) - two very different
// things to show a user.
export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `request failed with ${status}`)
    this.status = status
    this.detail = detail
  }
}

async function readDetail(res) {
  try {
    const body = await res.json()
    // FastAPI puts the message in `detail`. Validation errors put a list there.
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) return body.detail.map((e) => e.msg).join('; ')
    return JSON.stringify(body)
  } catch {
    return `${res.status} ${res.statusText}`
  }
}

export async function api(path, { method = 'GET', body, token = savedToken() } = {}) {
  const res = await fetch(path, {
    method,
    headers: {
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      // "Bearer" is just the convention: whoever bears this token is treated as
      // the user named inside it.
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new ApiError(res.status, await readDetail(res))
  return res.json()
}

export const login = (email, password) =>
  api('/api/auth/login', { method: 'POST', body: { email, password }, token: null })

export const logout = () => api('/api/auth/logout', { method: 'POST' })

export const me = (token) => api('/api/auth/me', { token })

export const demoUsers = () => api('/api/auth/demo-users', { token: null })

export const rbacMatrix = () => api('/api/rbac-matrix', { token: null })

export const health = () => api('/api/health', { token: null })

export const simulateOptions = () => api('/api/simulate/options')

export const simulate = (key, body = {}) =>
  api(`/api/simulate/${key}`, { method: 'POST', body })

// Phase 3: Harmonization Endpoints
export const previewHarmonization = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  
  const token = savedToken()
  const res = await fetch('/api/harmonization/preview', {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  })
  if (!res.ok) throw new ApiError(res.status, await readDetail(res))
  return res.json()
}

export const commitHarmonization = (body) =>
  api('/api/harmonization/commit', { method: 'POST', body })

// The WebSocket cannot send an Authorization header, so the token rides in the
// query string instead. Same server-side check either way.
export function liveUrl(token) {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${scheme}://${window.location.host}/ws/dashboard?token=${encodeURIComponent(token)}`
}
