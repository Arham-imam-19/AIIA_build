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

export const patientLogin = (email, password) =>
  api('/api/auth/patient/login', { method: 'POST', body: { email, password }, token: null })

export const logout = () => api('/api/auth/logout', { method: 'POST' })

export const me = (token) => api('/api/auth/me', { token })

export const demoUsers = () => api('/api/auth/demo-users', { token: null })

export const patientDemoUsers = () =>
  api('/api/auth/patient/demo-users', { token: null })

export const rbacMatrix = () => api('/api/rbac-matrix', { token: null })

export const health = () => api('/api/health', { token: null })

export const simulateOptions = () => api('/api/simulate/options')

export const simulate = (key, body = {}) =>
  api(`/api/simulate/${key}`, { method: 'POST', body })

export const listPatientRequests = (params = {}) => {
  const query = new URLSearchParams(params).toString()
  return api(`/api/patient-requests${query ? `?${query}` : ''}`)
}

export const createPatientRequest = (body) =>
  api('/api/patient-requests', { method: 'POST', body })

export const respondPatientRequest = (id, body) =>
  api(`/api/patient-requests/${id}/respond`, { method: 'PATCH', body })

export const createSite = (body) =>
  api('/api/sites', { method: 'POST', body })

export const fetchSites = (params = {}) => {
  const query = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') {
      query.append(k, v)
    }
  }
  const qStr = query.toString()
  return api(`/api/sites${qStr ? `?${qStr}` : ''}`)
}

export const createUser = (body) =>
  api('/api/users', { method: 'POST', body })

export const fetchUsers = (params = {}) => {
  const query = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') {
      query.append(k, v)
    }
  }
  const qStr = query.toString()
  return api(`/api/users${qStr ? `?${qStr}` : ''}`)
}

export const updateUser = (userId, body) =>
  api(`/api/users/${userId}`, { method: 'PATCH', body })

export const getMyEConsent = () => api('/api/econsent/my')

export const signEConsent = (body) =>
  api('/api/econsent/sign', { method: 'POST', body })

export const getSubjectEConsent = (subjectId) =>
  api(`/api/econsent/subjects/${subjectId}`)

export const getSubjectFhirConsent = (subjectId) =>
  api(`/api/econsent/subjects/${subjectId}/fhir`)

export const getSubjectAbdmConsent = (subjectId) =>
  api(`/api/econsent/subjects/${subjectId}/abdm-artefact`)

export const fetchAuditLogs = (params = {}) => {
  const query = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') {
      query.append(k, v)
    }
  }
  const qStr = query.toString()
  return api(`/api/audit-log${qStr ? `?${qStr}` : ''}`)
}

export const updateEthicsApproval = (trialId, body) =>
  api(`/api/trials/${trialId}/ethics-approval`, { method: 'PATCH', body })

export const fetchSubjectDossier = (subjectId) =>
  api(`/api/subjects/${subjectId}/dossier`)

export const createStructuredSubject = (body) =>
  api('/api/subjects', { method: 'POST', body })

export const createAdverseEvent = (body) =>
  api('/api/adverse-events', { method: 'POST', body })

export const logProtocolDeviation = (body) =>
  api('/api/protocol-deviations', { method: 'POST', body })

export const fetchSubjects = (params = {}) => {
  const query = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') {
      query.append(k, v)
    }
  }
  const qStr = query.toString()
  return api(`/api/subjects${qStr ? `?${qStr}` : ''}`)
}

export const fetchTrialCdiscJson = (trialId) =>
  api(`/api/trials/${trialId}/export/cdisc-json`)

export const fetchTrialFhirBundle = (trialId) =>
  api(`/api/trials/${trialId}/export/fhir-bundle`)

export const fetchSubjectFhirBundle = (subjectId) =>
  api(`/api/subjects/${subjectId}/export/fhir`)

export async function downloadTrialCdiscSdtmZip(trialId, token = savedToken()) {
  const res = await fetch(
    `/api/trials/${encodeURIComponent(trialId)}/export/cdisc-sdtm.zip`,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
  )
  if (!res.ok) throw new ApiError(res.status, await readDetail(res))

  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^";]+)"?/i)
  const filename = match?.[1] || `CDISC_SDTM_Trial_${trialId}.zip`
  const url = URL.createObjectURL(await res.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 0)
  return filename
}

export const fetchTrials = () => api('/api/trials')

export async function downloadSafetyReport(eventId, token = savedToken()) {
  const res = await fetch(
    `/api/adverse-events/${encodeURIComponent(eventId)}/safety-report.pdf`,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
  )
  if (!res.ok) throw new ApiError(res.status, await readDetail(res))

  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^";]+)"?/i)
  const filename = match?.[1] || `safety-report-${eventId}.pdf`
  const url = URL.createObjectURL(await res.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 0)
  return filename
}

// The WebSocket cannot send an Authorization header, so the token rides in the
// query string instead. Same server-side check either way.
export function liveUrl(token) {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${scheme}://${window.location.host}/ws/dashboard?token=${encodeURIComponent(token)}`
}
