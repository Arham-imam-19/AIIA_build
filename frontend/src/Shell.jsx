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
    ...((user.role !== 'admin' && (user.role === 'coordinator' || user.permissions?.includes('subject:write')))
      ? [
          ['screen_participant', 'Screen New Participant'],
        ]
      : []),
    ...((user.role !== 'admin' && (user.role === 'coordinator' || user.role === 'principal_investigator' || user.role === 'institution_admin' || user.permissions?.includes('subject:read')))
      ? [
          ['view_participants', 'View Participants'],
        ]
      : []),
    ...(user.role === 'admin'
      ? [
          ['infrastructure', 'Clinical Infrastructure & Actions'],
          ['create_account', '+ Create New Account'],
          ['cdisc_ingest', 'CDISC Harmonizer (Import)'],
        ]
      : []),
    ...((user.role !== 'sponsor' && (user.permissions?.includes('export') || user.role === 'regulator' || user.role === 'coordinator' || user.role === 'admin'))
      ? [
          ['cdisc_export', 'CDISC Harmonizer (Export)'],
        ]
      : []),
    ['access', 'Access Rules & Matrix'],
  ]

  return (
    <div className="min-h-full bg-slate-100 text-slate-900 font-sans">
      {/* Top Ministry / Institutional Header Bar */}
      <header className="border-b border-slate-300 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div className="min-w-0">
            <div className="text-[10px] font-bold tracking-widest uppercase text-slate-500">
              Government of India &middot; Ministry of Ayush
            </div>
            <h1 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight mt-0.5">
              All India Institute of Ayurveda &mdash; Clinical Trials Management System
            </h1>
            <div className="text-xs text-slate-600 mt-0.5">
              Central CTMS Portal &middot; National Ayush Multi-Centric Clinical Research Network
            </div>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
            <div className="text-left sm:text-right text-xs">
              <div className="font-semibold text-slate-900">{user.full_name}</div>
              <div className="text-slate-500 text-[11px]">
                {user.role_label} &middot; <span className="font-medium text-slate-700">{scope}</span>
              </div>
            </div>
            <LivePill
              status={live.status}
              backend={live.dashboard?.live?.backend}
              updatedAt={live.updatedAt}
              onRefresh={live.refresh}
            />
          </div>
        </div>

        {/* Horizontal Main Navigation Bar */}
        <div className="border-t border-slate-300 bg-slate-900 text-white">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between px-6">
            <nav className="flex flex-wrap">
              {navItems.map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setView(key)}
                  className={`border-r border-slate-800 px-4 py-2.5 text-xs font-semibold tracking-wide transition ${
                    view === key
                      ? 'bg-slate-800 text-white border-b-2 border-b-white'
                      : 'text-slate-300 hover:bg-slate-800/80 hover:text-white'
                  }`}
                >
                  {label}
                </button>
              ))}
            </nav>
            <div className="py-1 sm:py-0">
              <button
                onClick={signOut}
                className="border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-700 transition"
              >
                Sign Out
              </button>
            </div>
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
