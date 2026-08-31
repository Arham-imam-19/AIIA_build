// Phase 2: log in, get the dashboard your role is entitled to, watch it update
// itself.
//
// There is no role switcher and no ?role= anywhere. The dashboard that renders
// is decided by the token, which is signed by the server - so the only way to see
// the Sponsor's screen is to log in as the Sponsor.
//
// Phase 1's landing page proved the chain React -> FastAPI -> PostgreSQL. That
// job is now done by the login screen's status hints and the footer.

import { useEffect, useRef, useState } from 'react'
import { AuthProvider, useAuth } from './auth'
import Login from './Login'
import RbacMatrix from './RbacMatrix'
import Shell from './Shell'
import { DASHBOARDS, FALLBACK } from './dashboards'
import { useLiveDashboard } from './useLiveDashboard'

// Which tiles changed since the last message, so they can flash. Comparing
// values rather than trusting the event means a tile only lights up if its
// number actually moved.
function useChangedTiles(dashboard) {
  const previous = useRef(null)
  const [changed, setChanged] = useState(new Set())

  useEffect(() => {
    if (!dashboard?.tiles) return
    const now = {}
    for (const tile of dashboard.tiles) now[tile.key] = tile.value

    if (previous.current) {
      const moved = new Set(
        Object.keys(now).filter((key) => previous.current[key] !== now[key]),
      )
      previous.current = now
      if (moved.size === 0) return
      setChanged(moved)
      // Clear the highlight so the next change is visible as a change.
      const timer = setTimeout(() => setChanged(new Set()), 2500)
      return () => clearTimeout(timer)
    }
    previous.current = now
  }, [dashboard])

  return changed
}

function SignedIn() {
  const { user, token, expire } = useAuth()
  const [view, setView] = useState('dashboard')
  const live = useLiveDashboard(token, { onExpired: expire })
  const changed = useChangedTiles(live.dashboard)

  const Dashboard = DASHBOARDS[user.role] || FALLBACK

  return (
    <Shell view={view} setView={setView} live={live}>
      {view === 'access' ? (
        <RbacMatrix highlightRole={user.role} />
      ) : live.status === 'refused' ? (
        <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{live.error}</p>
      ) : !live.dashboard ? (
        <p className="text-sm text-slate-400">Loading your dashboard…</p>
      ) : !live.dashboard.seeded ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-800">
          {live.dashboard.message}
          <code className="mt-1.5 block font-mono text-xs">
            docker compose exec backend python scripts/seed.py
          </code>
        </div>
      ) : (
        <Dashboard
          dashboard={live.dashboard}
          changed={changed}
          lastEvent={live.lastEvent}
          onExpired={expire}
        />
      )}
    </Shell>
  )
}

function Gate() {
  const { state } = useAuth()
  const patientPortal = window.location.pathname === '/patient-login'
  if (state === 'checking') {
    return (
      <div className="flex min-h-full items-center justify-center text-sm text-slate-400">
        Checking your session…
      </div>
    )
  }
  return state === 'signed-in' ? <SignedIn /> : <Login patientPortal={patientPortal} />
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  )
}
