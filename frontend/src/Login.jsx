// The login screen, with the five demo personas one click away.
//
// The persona list comes from /api/auth/demo-users, which only answers in
// development - printing credentials from an API would be indefensible anywhere
// else. Every account is synthetic; there is no real person and no real password
// anywhere in this system.

import { useEffect, useState } from 'react'
import { demoUsers, health, patientDemoUsers } from './api'
import { useAuth } from './auth'

const ROLE_BLURB = {
  admin: 'Primary Admin: manages institutions & system oversight',
  institution_admin: 'manages hospital site, researchers & patient inquiries',
  principal_investigator: 'Lead Researcher: runs clinical trial at the site',
  coordinator: 'books visits, enters data & coordinates care',
  monitor: 'Clinical Research Associate: verifies data and raises queries',
  sponsor: 'funds the trial and watches progress across all sites',
  ethics_committee: 'reviews safety events and protocol deviations',
  pharmacovigilance: 'codes adverse events and tracks NDCT timelines',
  regulator: 'inspects CTRI registration and the audit trail',
  dsmb: 'reviews aggregate safety data to halt or modify trials',
}

const getBlurb = (user, patientPortal) => {
  if (patientPortal) return 'trial participant: view schedule & message hospital admin'
  if (user.email === 'director@demo.aiia-ctms.in') return 'Has global portfolio access'
  if (user.email === 'investor@himalaya.com') return 'Access scoped strictly to funded trials'
  return ROLE_BLURB[user.role]
}

export default function Login({ patientPortal = false }) {
  const { signIn, state } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [demo, setDemo] = useState(null)
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const loadDemoUsers = patientPortal ? patientDemoUsers : demoUsers
    loadDemoUsers()
      .then((data) => {
        setDemo(data)
        if (data.users.length) {
          // Pre-fill the investigator: the first persona of the walkthrough.
          setEmail(data.users[0].email)
          setPassword(data.password)
        }
      })
      .catch(() => setDemo(null))
    health()
      .then(setStatus)
      .catch(() => setStatus(null))
  }, [patientPortal])

  // The persona buttons pass their credentials in explicitly. Calling
  // setPassword() and then reading `password` in the same handler would send the
  // *previous* password - React state updates do not apply until the next render.
  async function submit(event, asEmail = email, asPassword = password) {
    event?.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await signIn(asEmail, asPassword, patientPortal)
    } catch (err) {
      setError(err.detail || err.message)
    } finally {
      setBusy(false)
    }
  }

  const seeded = status?.schema?.tables > 0

  return (
    <div className="flex min-h-full items-center justify-center bg-slate-50 px-6 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <h1 className="text-lg font-semibold tracking-tight text-slate-900">
            {patientPortal ? 'Patient Portal' : 'Staff Portal'}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Ayurveda CTMS &middot; Ministry of Ayush &middot; SIH26046
          </p>
        </div>

        <form
          onSubmit={submit}
          className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
        >
          <label className="block text-xs font-medium text-slate-600" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm text-slate-800 outline-none focus:border-aiia-500"
          />

          <label
            className="mt-4 block text-xs font-medium text-slate-600"
            htmlFor="password"
          >
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm text-slate-800 outline-none focus:border-aiia-500"
          />

          <button
            type="submit"
            disabled={busy || state === 'checking'}
            className="mt-5 w-full rounded-lg bg-aiia-600 py-2 text-sm font-medium text-white transition hover:bg-aiia-700 disabled:bg-slate-300"
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>

          {state === 'expired' && !error && (
            <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Your session ended. Sign in again.
            </p>
          )}

          {error && (
            <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
              {error}
            </p>
          )}
        </form>

        {demo?.users?.length > 0 && (
          <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Demo personas
            </h2>
            <p className="mt-1 text-xs text-slate-400">{demo.note}</p>
            <ul className="mt-3 space-y-1.5">
              {demo.users.map((user) => (
                <li key={user.email}>
                  <button
                    onClick={(e) => {
                      setEmail(user.email)
                      setPassword(demo.password)
                      submit(e, user.email, demo.password)
                    }}
                    disabled={busy}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-left transition hover:border-aiia-500 hover:bg-aiia-50 disabled:opacity-50"
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-sm font-medium text-slate-800">
                        {user.email === 'director@demo.aiia-ctms.in' ? 'Institutional Leadership (AIIA Director)' : user.email === 'investor@himalaya.com' ? 'External Funder (Himalaya)' : user.role_label}
                      </span>
                      <span className="text-xs text-slate-400">
                        {getBlurb(user, patientPortal)}
                      </span>
                    </div>
                    <div className="mt-0.5 font-mono text-xs text-slate-500">
                      {user.email}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
            <p className="mt-3 border-t border-slate-100 pt-2 font-mono text-xs text-slate-400">
              password: {demo.password}
            </p>
          </div>
        )}

        {status && !seeded && (
          <p className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-xs leading-relaxed text-amber-800">
            The database has no tables yet. Bring the stack up, then load the synthetic
            trial:
            <code className="mt-1 block font-mono">
              docker compose exec backend python scripts/seed.py
            </code>
          </p>
        )}

        {!demo && status && seeded && (
          <p className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-xs leading-relaxed text-amber-800">
            No demo accounts found. Give the seeded users their passwords:
            <code className="mt-1 block font-mono">
              docker compose exec backend python scripts/seed.py --passwords
            </code>
          </p>
        )}

        <p className="mt-6 text-center text-xs text-slate-400">
          All data in this system is synthetic. No real patient data.
        </p>
        <p className="mt-3 text-center text-sm">
          <a
            href={patientPortal ? '/' : '/patient-login'}
            className="text-aiia-600 hover:text-aiia-700 hover:underline"
          >
            {patientPortal ? 'Go to staff portal' : 'Go to patient portal'}
          </a>
        </p>
      </div>
    </div>
  )
}
