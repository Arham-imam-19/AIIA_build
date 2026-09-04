// Phase 2: log in, get the dashboard your role is entitled to, watch it update
// itself.

import { useEffect, useRef, useState } from 'react'
import { AuthProvider, useAuth } from './auth'
import CreateUserPage from './pages/CreateUserPage'
import InfrastructurePage from './pages/InfrastructurePage'
import HarmonizationPage from './pages/HarmonizationPage'
import ExportPage from './pages/ExportPage'
import ScreenParticipantPage from './pages/ScreenParticipantPage'
import ParticipantsListPage from './pages/ParticipantsListPage'
import PatientDetailPage from './pages/PatientDetailPage'
import Login from './Login'
import RbacMatrix from './RbacMatrix'
import Shell from './Shell'
import { DASHBOARDS, FALLBACK } from './dashboards'
import { useLiveDashboard } from './useLiveDashboard'

// Which tiles changed since the last message, so they can flash.
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
  const [selectedSubjectId, setSelectedSubjectId] = useState(null)
  const [screeningSuccessPopup, setScreeningSuccessPopup] = useState(null)
  const live = useLiveDashboard(token, { onExpired: expire })
  const changed = useChangedTiles(live.dashboard)

  const Dashboard = DASHBOARDS[user.role] || FALLBACK

  return (
    <Shell view={view} setView={setView} live={live}>
      {/* Screening Success Modal Dialog */}
      {screeningSuccessPopup && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4">
          <div className="w-full max-w-md border-2 border-slate-900 bg-white p-6 shadow-2xl">
            <div className="border-b border-slate-200 pb-3">
              <div className="flex items-center gap-2 text-emerald-800 font-bold uppercase tracking-wider text-xs">
                <span className="flex h-4 w-4 items-center justify-center bg-emerald-600 text-white text-[10px] font-bold">✓</span>
                Screening Intake Successful
              </div>
              <h2 className="mt-2 text-xl font-bold uppercase text-slate-900 font-mono">
                {screeningSuccessPopup.subject_code}
              </h2>
            </div>
            <div className="py-4 text-xs text-slate-700 space-y-2">
              <p>
                The participant has been registered into the trial registry. System-generated de-identified parameters and digital audit provenance have been recorded.
              </p>
              <div className="border border-slate-200 bg-slate-50 p-2.5 font-mono text-[11px] text-slate-700">
                Screening Status: <strong>{screeningSuccessPopup.status?.toUpperCase()}</strong> &middot; Site: <strong>{screeningSuccessPopup.site_id}</strong>
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2.5 pt-3 border-t border-slate-200">
              <button
                type="button"
                onClick={() => setScreeningSuccessPopup(null)}
                className="border border-slate-400 bg-white px-4 py-2 text-xs font-bold uppercase tracking-wider text-slate-800 hover:bg-slate-100"
              >
                Dismiss to Dashboard
              </button>
              <button
                type="button"
                onClick={() => {
                  const subId = screeningSuccessPopup.id
                  setScreeningSuccessPopup(null)
                  setSelectedSubjectId(subId)
                  setView('patient_detail')
                }}
                className="border border-slate-900 bg-slate-900 px-4 py-2 text-xs font-bold uppercase tracking-wider text-white hover:bg-slate-800"
              >
                View Patient Detail &amp; Log &rarr;
              </button>
            </div>
          </div>
        </div>
      )}

      {view === 'cdisc_export' ? (
        <ExportPage />
      ) : view === 'cdisc_ingest' ? (
        <HarmonizationPage />
      ) : view === 'screen_participant' ? (
        <ScreenParticipantPage
          onNavigateDashboard={() => setView('dashboard')}
          onRefresh={live.refresh}
          onScreenSuccess={(res) => {
            setScreeningSuccessPopup(res)
            setView('dashboard')
          }}
        />
      ) : view === 'view_participants' ? (
        <ParticipantsListPage
          onSelectPatient={(id) => {
            setSelectedSubjectId(id)
            setView('patient_detail')
          }}
          onNavigateScreenParticipant={() => setView('screen_participant')}
        />
      ) : view === 'patient_detail' ? (
        selectedSubjectId ? (
          <PatientDetailPage
            subjectId={selectedSubjectId}
            onBack={() => {
              setSelectedSubjectId(null)
              setView('view_participants')
            }}
            onRefresh={live.refresh}
          />
        ) : (
          <ParticipantsListPage
            onSelectPatient={(id) => {
              setSelectedSubjectId(id)
              setView('patient_detail')
            }}
            onNavigateScreenParticipant={() => setView('screen_participant')}
          />
        )
      ) : view === 'infrastructure' ? (
        <InfrastructurePage onNavigateDashboard={() => setView('dashboard')} />
      ) : view === 'create_account' ? (
        <CreateUserPage onNavigateDashboard={() => setView('dashboard')} />
      ) : view === 'access' ? (
        <RbacMatrix highlightRole={user.role} />
      ) : live.status === 'refused' ? (
        <p className="border border-red-300 bg-red-50 p-4 text-xs font-semibold text-red-800">{live.error}</p>
      ) : !live.dashboard ? (
        <p className="text-xs text-slate-500">Loading dashboard...</p>
      ) : !live.dashboard.seeded ? (
        <div className="border border-amber-300 bg-amber-50 p-4 text-xs leading-relaxed text-amber-900">
          {live.dashboard.message}
          <code className="mt-1.5 block font-mono text-[11px]">
            docker compose exec backend python scripts/seed.py
          </code>
        </div>
      ) : (
        <Dashboard
          dashboard={live.dashboard}
          changed={changed}
          lastEvent={live.lastEvent}
          onExpired={expire}
          onRefresh={live.refresh}
          onNavigateCreateUser={() => setView('create_account')}
          onNavigateInfrastructure={() => setView('infrastructure')}
          onNavigateScreenParticipant={() => setView('screen_participant')}
          onNavigateParticipants={() => setView('view_participants')}
          onSelectPatient={(id) => {
            setSelectedSubjectId(id)
            setView('patient_detail')
          }}
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
