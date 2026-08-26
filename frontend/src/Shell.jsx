// The signed-in frame: who you are, whether the live line is up, and a way out.

import { useEffect, useState } from 'react'
import { health } from './api'
import { useAuth } from './auth'

const LIVE_LABEL = {
  connecting: ['Connecting…', 'bg-amber-400 animate-pulse'],
  live: ['Live', 'bg-emerald-500'],
  reconnecting: ['Reconnecting…', 'bg-amber-400 animate-pulse'],
  refused: ['Not live', 'bg-red-500'],
}

function LivePill({ status, backend, updatedAt, onRefresh }) {
  const [label, dot] = LIVE_LABEL[status] || LIVE_LABEL.connecting
  const time = updatedAt ? new Date(updatedAt).toLocaleTimeString() : null
  return (
    <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1">
      <span className={`inline-block h-2 w-2 rounded-full ${dot}`} />
      <span className="text-xs font-medium text-slate-600">{label}</span>
      {backend && (
        <span
          className="font-mono text-xs text-slate-400"
          title={
            backend === 'redis'
              ? 'Redis pub/sub: updates cross every backend container.'
              : 'In-process fan-out: Redis is unavailable, so updates reach this container only.'
          }
        >
          {backend}
        </span>
      )}
      {time && <span className="text-xs text-slate-400">· {time}</span>}
      <button
        onClick={onRefresh}
        title="Ask the server to resend the numbers"
        className="ml-0.5 text-xs text-slate-400 underline hover:text-slate-600"
      >
        refresh
      </button>
    </div>
  )
}

export default function Shell({ view, setView, live, children }) {
  const { user, signOut } = useAuth()
  const [sys, setSys] = useState(null)

  useEffect(() => {
    health()
      .then(setSys)
      .catch(() => setSys(null))
  }, [])

  const scope = user.site_scoped
    ? `site ${user.site_id ?? '—'} only`
    : 'all sites'

  return (
    <div className="min-h-full bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-4">
          <div className="min-w-0">
            <h1 className="truncate text-base font-semibold tracking-tight">
              AIIA Clinical Trials Dashboard
            </h1>
            <p className="truncate text-xs text-slate-500">
              {user.full_name} &middot;{' '}
              <span className="font-medium text-aiia-700">{user.role_label}</span> &middot;{' '}
              {scope}
              {user.organization ? ` · ${user.organization}` : ''}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <LivePill
              status={live.status}
              backend={live.dashboard?.live?.backend}
              updatedAt={live.updatedAt}
              onRefresh={live.refresh}
            />
            <nav className="flex overflow-hidden rounded-lg border border-slate-200">
              {[
                ['dashboard', 'Dashboard'],
                ['access', 'Access rules'],
                ['harmonization', 'CDISC Ingestion'],
              ]
                .filter(([key]) => key !== 'harmonization' || ['admin', 'coordinator', 'principal_investigator'].includes(user.role))
                .map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setView(key)}
                  className={`px-3 py-1.5 text-xs font-medium transition ${
                    view === key
                      ? 'bg-aiia-600 text-white'
                      : 'bg-white text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {label}
                </button>
              ))}
            </nav>
            <button
              onClick={signOut}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-50"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">{children}</main>

      <footer className="mx-auto max-w-6xl px-6 pb-8 text-center text-xs text-slate-400">
        {live.dashboard?.data_notice || 'All data is synthetic. No real patient data.'}
        {sys && (
          <>
            {' · '}
            {sys.schema.tables} tables · rev {sys.schema.migration_revision ?? '–'} ·{' '}
            {sys.environment}
          </>
        )}
        {' · '}
        <a
          className="underline hover:text-slate-600"
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noreferrer"
        >
          API docs
        </a>
      </footer>
    </div>
  )
}
