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
    <div className="flex items-center gap-2 border border-slate-300 bg-white px-2.5 py-1 text-xs">
      <span className={`inline-block h-2 w-2 ${dot}`} />
      <span className="font-medium text-slate-700">{label}</span>
      {backend && (
        <span
          className="font-mono text-slate-500"
          title={
            backend === 'redis'
              ? 'Redis pub/sub: updates cross every backend container.'
              : 'In-process fan-out: Redis is unavailable, so updates reach this container only.'
          }
        >
          {backend}
        </span>
      )}
      {time && <span className="text-slate-400">· {time}</span>}
      <button
        onClick={onRefresh}
        title="Ask the server to resend the numbers"
        className="ml-0.5 text-slate-500 underline hover:text-slate-800"
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
    ? `Site ${user.site_id ?? '—'} only`
    : 'All participating sites'

  const navItems = [
    ['dashboard', 'Dashboard'],
    ...(user.role === 'admin' ? [['create_account', '+ Create New Account']] : []),
    ['access', 'Access Rules'],
  ]

  return (
    <div className="min-h-full bg-slate-100 text-slate-900 font-sans">
      <header className="border-b border-slate-300 bg-white shadow-sm">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-6 py-3.5">
          <div className="min-w-0">
            <div className="text-[10px] font-bold tracking-wider uppercase text-slate-500">
              Ministry of Ayush &middot; Government of India
            </div>
            <h1 className="truncate text-base font-bold text-slate-900 tracking-tight">
              All India Institute of Ayurveda &mdash; Clinical Trials Portal (CTMS)
            </h1>
            <p className="truncate text-xs text-slate-600">
              User: <span className="font-semibold text-slate-900">{user.full_name}</span> &middot;{' '}
              Role: <span className="font-semibold text-slate-900">{user.role_label}</span> &middot;{' '}
              Jurisdiction: <span className="font-medium text-slate-700">{scope}</span>
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
            <nav className="flex border border-slate-300 bg-white">
              {navItems.map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setView(key)}
                  className={`border-r border-slate-300 last:border-r-0 px-3.5 py-1.5 text-xs font-semibold transition ${
                    view === key
                      ? 'bg-slate-800 text-white'
                      : 'bg-white text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  {label}
                </button>
              ))}
            </nav>
            <button
              onClick={signOut}
              className="border border-slate-300 bg-slate-50 px-3.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-200 transition"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-6">{children}</main>

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
