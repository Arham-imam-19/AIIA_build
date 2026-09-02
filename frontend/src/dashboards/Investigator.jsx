import { useEffect, useState } from 'react'
import { fetchTrials } from '../api'
import DashboardLayout from './layout'
import ParticipantIntakeModal from '../components/ParticipantIntakeModal'
import ReportAdverseEventModal from '../components/ReportAdverseEventModal'
import LogProtocolDeviationModal from '../components/LogProtocolDeviationModal'
import ParticipantDossierModal from '../components/ParticipantDossierModal'

function SiteComplianceStatusBanner() {
  const [trial, setTrial] = useState(null)

  useEffect(() => {
    fetchTrials()
      .then((res) => {
        if (res.items?.[0]) setTrial(res.items[0])
      })
      .catch(() => {})
  }, [])

  const isEthicsApproved = trial?.ethics_approval_status === 'approved'
  const isCtriRegistered = Boolean(trial?.ctri_number && trial?.ctri_number.trim())
  const isFullyCleared = isEthicsApproved && isCtriRegistered

  return (
    <div className={`flex items-center justify-between rounded-lg border px-4 py-2.5 text-xs ${
      isFullyCleared
        ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
        : 'border-amber-200 bg-amber-50 text-amber-900'
    }`}>
      <span className="flex items-center gap-2 font-medium">
        <span className={`flex h-2 w-2 rounded-full ${isFullyCleared ? 'bg-emerald-600' : 'bg-amber-600'}`}></span>
        {isFullyCleared
          ? `✅ Regulatory & Ethics Cleared (${trial.ethics_approval_number || 'IEC Approved'} | ${trial.ctri_number}): Site authorized to recruit.`
          : !isEthicsApproved
          ? `⚠️ Enrollment On Hold: Trial ethics approval is ${trial?.ethics_approval_status || 'Pending'}. Software blocks enrollment until IEC approves.`
          : `⚠️ Enrollment On Hold: Prospective CTRI registration required before participant screening (NDCT Rules 2019).`}
      </span>
      <span className="hidden sm:inline font-mono text-[11px]">
        NDCT Rules 2019 Rule 22
      </span>
    </div>
  )
}

export default function Investigator(props) {
  const [showIntakeModal, setShowIntakeModal] = useState(false)
  const [showAeModal, setShowAeModal] = useState(false)
  const [showDeviationModal, setShowDeviationModal] = useState(false)
  const [selectedSubjectId, setSelectedSubjectId] = useState(null)

  return (
    <div className="space-y-4">
      <SiteComplianceStatusBanner />

      {/* Clinical Site Actions Center */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <span className="flex h-2 w-2 rounded-full bg-aiia-600"></span>
              Principal Investigator Clinical & Safety Actions
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Execute structured CDASH screening intake, evaluate & report MedDRA adverse events, and log deviations.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setShowIntakeModal(true)}
              className="flex items-center gap-1.5 rounded-lg bg-aiia-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-aiia-700 transition"
            >
              📝 Screen New Participant
            </button>
            <button
              onClick={() => setShowAeModal(true)}
              className="flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-red-700 transition"
            >
              🚨 Report Adverse Event
            </button>
            <button
              onClick={() => setShowDeviationModal(true)}
              className="flex items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-amber-700 transition"
            >
              ⚠️ Log Protocol Deviation
            </button>
            <button
              onClick={() => setSelectedSubjectId(1)}
              className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800 transition"
            >
              🔍 Inspect Participant Dossier
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
      {showIntakeModal && (
        <ParticipantIntakeModal
          onClose={() => setShowIntakeModal(false)}
          onSuccess={props.onRefresh}
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
      {selectedSubjectId && (
        <ParticipantDossierModal
          subjectId={selectedSubjectId}
          onClose={() => setSelectedSubjectId(null)}
        />
      )}
    </div>
  )
}
