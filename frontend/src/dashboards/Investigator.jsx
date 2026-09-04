import { useEffect, useState } from 'react'
import { fetchTrials, updateTrialStatus, activateTrial } from '../api'
import DashboardLayout from './layout'
import ParticipantIntakeModal from '../components/ParticipantIntakeModal'
import ReportAdverseEventModal from '../components/ReportAdverseEventModal'
import LogProtocolDeviationModal from '../components/LogProtocolDeviationModal'
import ParticipantDossierModal from '../components/ParticipantDossierModal'
import RegisterCtriModal from '../components/RegisterCtriModal'
import CreateTrialModal from '../components/CreateTrialModal'

const statusColors = {
  planning: 'bg-slate-100 text-slate-800 border-slate-300',
  pending_ethics: 'bg-amber-50 text-amber-800 border-amber-300',
  approved: 'bg-blue-50 text-blue-800 border-blue-300',
  recruiting: 'bg-emerald-50 text-emerald-800 border-emerald-300',
  active: 'bg-emerald-100 text-emerald-900 border-emerald-400',
  suspended: 'bg-red-50 text-red-800 border-red-300',
  completed: 'bg-slate-100 text-slate-800 border-slate-300',
  terminated: 'bg-red-100 text-red-900 border-red-400',
}

function SiteComplianceStatusBanner({ trial }) {
  if (!trial) return null
  const isEthicsApproved = trial.ethics_approval_status === 'approved'
  const isCtriRegistered = Boolean(trial.ctri_number && trial.ctri_number.trim())
  const isRecruiting = trial.status === 'recruiting' || trial.status === 'active'

  return (
    <div className={`flex flex-wrap items-center justify-between gap-2 rounded-lg border px-4 py-2.5 text-xs ${
      isRecruiting
        ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
        : 'border-amber-200 bg-amber-50 text-amber-900'
    }`}>
      <span className="flex items-center gap-2 font-medium">
        <span className={`flex h-2 w-2 rounded-full ${isRecruiting ? 'bg-emerald-600' : 'bg-amber-600'}`}></span>
        {isRecruiting
          ? `✅ Trial is in ${trial.status.toUpperCase()} status (${trial.ethics_approval_number || 'IEC Cleared'} | ${trial.ctri_number || 'CTRI Registered'}): Site is actively authorized to recruit & screen.`
          : !isEthicsApproved
          ? `⚠️ Protocol is currently in ${trial.status?.toUpperCase()} (${trial.ethics_approval_status ? trial.ethics_approval_status.toUpperCase() : 'PENDING ETHICS'}). You can transition status using the controls below.`
          : `⚠️ Protocol is in ${trial.status?.toUpperCase()}. Use the controls below to activate recruitment.`}
      </span>
      <span className="hidden sm:inline font-mono text-[11px]">
        NDCT Rules 2019 Rule 22
      </span>
    </div>
  )
}

export default function Investigator(props) {
  const [trials, setTrials] = useState([])
  const [selectedTrialId, setSelectedTrialId] = useState(null)
  const [showCreateTrialModal, setShowCreateTrialModal] = useState(false)
  const [showIntakeModal, setShowIntakeModal] = useState(false)
  const [showAeModal, setShowAeModal] = useState(false)
  const [showDeviationModal, setShowDeviationModal] = useState(false)
  const [showCtriModal, setShowCtriModal] = useState(false)
  const [selectedSubjectId, setSelectedSubjectId] = useState(null)
  const [statusBusy, setStatusBusy] = useState(false)
  const [statusMsg, setStatusMsg] = useState(null)
  const [statusErr, setStatusErr] = useState(null)

  function loadTrials() {
    fetchTrials({ institution_only: true })
      .then((res) => {
        const items = res.items || []
        setTrials(items)
        if (items.length > 0 && !selectedTrialId) {
          setSelectedTrialId(items[0].id)
        }
      })
      .catch(() => {})
  }

  useEffect(() => {
    loadTrials()
  }, [])

  const activeTrial = trials.find(t => t.id === selectedTrialId) || trials[0]

  async function handleQuickStatusChange(newStatus) {
    if (!activeTrial) return
    setStatusBusy(true)
    setStatusErr(null)
    setStatusMsg(null)
    try {
      await updateTrialStatus(activeTrial.id, {
        status: newStatus,
        reason: `Status transitioned to ${newStatus} by Principal Investigator.`
      })
      setStatusMsg(`Protocol ${activeTrial.protocol_number} status transitioned to ${newStatus.toUpperCase()}`)
      loadTrials()
      props.onRefresh?.()
      setTimeout(() => setStatusMsg(null), 4000)
    } catch (err) {
      setStatusErr(err.detail || err.message || 'Failed to update protocol status')
      setTimeout(() => setStatusErr(null), 5000)
    } finally {
      setStatusBusy(false)
    }
  }

  async function handleQuickActivate() {
    if (!activeTrial) return
    setStatusBusy(true)
    setStatusErr(null)
    setStatusMsg(null)
    try {
      await activateTrial(activeTrial.id)
      setStatusMsg(`Protocol ${activeTrial.protocol_number} successfully activated for recruitment!`)
      loadTrials()
      props.onRefresh?.()
      setTimeout(() => setStatusMsg(null), 4000)
    } catch (err) {
      // If activation strict gate fails, offer direct transition to recruiting
      try {
        await updateTrialStatus(activeTrial.id, {
          status: 'recruiting',
          reason: 'Recruitment activated by Principal Investigator.'
        })
        setStatusMsg(`Protocol ${activeTrial.protocol_number} status set to RECRUITING.`)
        loadTrials()
        props.onRefresh?.()
        setTimeout(() => setStatusMsg(null), 4000)
      } catch (err2) {
        setStatusErr(err.detail || err.message || 'Failed to activate trial')
        setTimeout(() => setStatusErr(null), 5000)
      }
    } finally {
      setStatusBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      {statusMsg && (
        <div className="rounded-lg border border-emerald-600 bg-emerald-50 p-3 text-xs font-bold text-emerald-900 shadow-sm flex items-center justify-between">
          <span>✅ {statusMsg}</span>
          <button onClick={() => setStatusMsg(null)} className="text-emerald-700 hover:text-emerald-950">✕</button>
        </div>
      )}

      {statusErr && (
        <div className="rounded-lg border border-red-600 bg-red-50 p-3 text-xs font-bold text-red-900 shadow-sm flex items-center justify-between">
          <span>⚠️ {statusErr}</span>
          <button onClick={() => setStatusErr(null)} className="text-red-700 hover:text-red-950">✕</button>
        </div>
      )}

      <SiteComplianceStatusBanner trial={activeTrial} />

      {/* Protocol Governance & Status Transition Controls for PI */}
      <div className="border border-slate-300 bg-white p-4 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
          <div className="w-full max-w-lg">
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-700 mb-1">
              Select Target Protocol (PI Governance)
            </label>
            <select
              value={selectedTrialId || ''}
              onChange={e => setSelectedTrialId(Number(e.target.value))}
              className="w-full border border-slate-300 p-2 text-xs font-semibold text-slate-900 focus:border-slate-800 focus:outline-none"
            >
              {trials.map(p => (
                <option key={p.id} value={p.id}>
                  [{p.protocol_number}] {p.short_title || p.title} &middot; Status: {p.status?.toUpperCase()}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowCreateTrialModal(true)}
              className="border border-blue-900 bg-blue-900 px-3.5 py-2 text-xs font-bold text-white hover:bg-blue-800 transition shadow-sm"
            >
              + Create New Protocol
            </button>
            <button
              onClick={() => setShowIntakeModal(true)}
              className="border border-emerald-700 bg-emerald-700 px-3.5 py-2 text-xs font-bold text-white hover:bg-emerald-800 transition shadow-sm"
            >
              📝 Screen New Participant
            </button>
          </div>
        </div>

        {activeTrial && (
          <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 border border-slate-200 p-3 text-xs">
            <div className="flex flex-wrap items-center gap-3">
              <div>
                <span className="text-[10px] font-bold uppercase text-slate-500 block">Current Status</span>
                <span className={`inline-block border px-2.5 py-0.5 font-mono text-[11px] font-bold uppercase mt-0.5 ${statusColors[activeTrial.status] || 'bg-slate-100 text-slate-800 border-slate-300'}`}>
                  {activeTrial.status}
                </span>
              </div>

              <div>
                <span className="text-[10px] font-bold uppercase text-slate-500 block">IEC Approval</span>
                <span className={`inline-block border px-2 py-0.5 font-mono text-[10px] font-bold uppercase mt-0.5 ${activeTrial.ethics_approval_status === 'approved' ? 'bg-emerald-50 text-emerald-800 border-emerald-300' : 'bg-amber-50 text-amber-800 border-amber-300'}`}>
                  {activeTrial.ethics_approval_status || 'Pending'}
                </span>
              </div>

              <div>
                <span className="text-[10px] font-bold uppercase text-slate-500 block">CTRI Registration</span>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className={`font-mono text-[11px] font-semibold ${activeTrial.ctri_number ? 'text-slate-800' : 'text-amber-700'}`}>
                    {activeTrial.ctri_number || 'Missing (Rule 22)'}
                  </span>
                  <button
                    onClick={() => setShowCtriModal(true)}
                    className="border border-slate-300 bg-white px-1.5 py-0.5 text-[10px] font-bold text-slate-700 hover:bg-slate-100 transition shadow-xs"
                  >
                    {activeTrial.ctri_number ? 'Edit' : '+ Register CTRI'}
                  </button>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <label className="text-[11px] font-bold uppercase text-slate-700">
                Change Protocol Status:
              </label>
              <select
                value={activeTrial.status}
                disabled={statusBusy}
                onChange={(e) => handleQuickStatusChange(e.target.value)}
                className="border border-slate-400 bg-white p-1.5 text-xs font-bold text-slate-900 focus:border-slate-800 focus:outline-none"
              >
                <option value="planning">PLANNING (Drafting)</option>
                <option value="pending_ethics">PENDING_ETHICS (Under Review)</option>
                <option value="approved">APPROVED (IEC Cleared)</option>
                <option value="recruiting">RECRUITING (Open for Screening)</option>
                <option value="active">ACTIVE (Treatment Stage)</option>
                <option value="suspended">SUSPENDED (Safety Hold)</option>
                <option value="completed">COMPLETED (Closed)</option>
                <option value="terminated">TERMINATED (Early Exit)</option>
              </select>

              {activeTrial.status !== 'recruiting' && (
                <button
                  onClick={handleQuickActivate}
                  disabled={statusBusy}
                  className="border border-emerald-700 bg-emerald-700 px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-white hover:bg-emerald-800 transition shadow-sm disabled:opacity-50"
                >
                  🚀 Activate Recruitment
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Clinical Site Actions Center */}
      <div className="border border-slate-300 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span className="flex h-2 w-2 rounded-full bg-slate-900"></span>
              Principal Investigator Clinical &amp; Safety Actions
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Execute structured CDASH screening intake, evaluate &amp; report MedDRA adverse events, and log deviations.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setShowIntakeModal(true)}
              className="border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-black transition"
            >
              📝 Screen New Participant
            </button>
            <button
              onClick={() => setShowAeModal(true)}
              className="border border-red-700 bg-red-700 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-red-800 transition"
            >
              🚨 Report Adverse Event
            </button>
            <button
              onClick={() => setShowDeviationModal(true)}
              className="border border-amber-600 bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-amber-700 transition"
            >
              ⚠️ Log Protocol Deviation
            </button>
            <button
              onClick={() => props.onNavigateParticipants?.()}
              className="border border-slate-400 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition"
            >
              🔍 View Participants &amp; Dossiers
            </button>
          </div>
        </div>
      </div>

      <DashboardLayout
        {...props}
        wide={['recent_aes']}
        note="Scoped to your site only. Safety first: an open adverse event is one that has not resolved yet, and a serious one has to reach the ethics committee within days."
      />

      {/* Modals */}
      {showCreateTrialModal && (
        <CreateTrialModal
          onClose={() => setShowCreateTrialModal(false)}
          onSuccess={() => {
            loadTrials()
            props.onRefresh?.()
          }}
        />
      )}
      {showIntakeModal && (
        <ParticipantIntakeModal
          trialId={selectedTrialId}
          onClose={() => setShowIntakeModal(false)}
          onSuccess={() => {
            loadTrials()
            props.onRefresh?.()
          }}
        />
      )}
      {showAeModal && (
        <ReportAdverseEventModal
          onClose={() => setShowAeModal(false)}
          onSuccess={props.onRefresh}
        />
      )}
      {showDeviationModal && (
        <LogProtocolDeviationModal
          onClose={() => setShowDeviationModal(false)}
          onSuccess={props.onRefresh}
        />
      )}
      {showCtriModal && activeTrial && (
        <RegisterCtriModal
          trial={activeTrial}
          onClose={() => setShowCtriModal(false)}
          onSuccess={() => {
            loadTrials()
            props.onRefresh?.()
          }}
        />
      )}
      {selectedSubjectId && (
        <ParticipantDossierModal
          subjectId={selectedSubjectId}
          onClose={() => setSelectedSubjectId(null)}
        />
      )}
    </div>
  )
}
