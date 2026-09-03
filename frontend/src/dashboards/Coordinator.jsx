import { useEffect, useState } from 'react'
import { fetchTrials, fetchCoordinatorSummary } from '../api'
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

export default function Coordinator(props) {
  const [showIntakeModal, setShowIntakeModal] = useState(false)
  const [showAeModal, setShowAeModal] = useState(false)
  const [showDeviationModal, setShowDeviationModal] = useState(false)
  const [selectedSubjectId, setSelectedSubjectId] = useState(null)
  const [summaryData, setSummaryData] = useState(null)

  const loadSummary = () => {
    fetchCoordinatorSummary()
      .then((data) => {
        if (data?.tiles?.length) setSummaryData(data)
      })
      .catch(() => {})
  }

  useEffect(() => {
    loadSummary()
  }, [])

  useEffect(() => {
    loadSummary()
  }, [props.dashboard, props.lastEvent])

  const handleRefreshAll = () => {
    loadSummary()
    props.onRefresh?.()
  }

  const activeDashboard = summaryData?.tiles ? {
    ...props.dashboard,
    tiles: summaryData.tiles,
  } : props.dashboard

  return (
    <div className="space-y-4">
      <SiteComplianceStatusBanner />

      <DashboardLayout
        {...props}
        dashboard={activeDashboard}
        wide={['upcoming', 'screening']}
        note="Your worklist for the next two weeks. An overdue visit becomes a protocol deviation if it slips outside its window, so these dates are the ones that matter."
      />

      {/* Modals */}
      {showIntakeModal && (
        <ParticipantIntakeModal
          onClose={() => setShowIntakeModal(false)}
          onSuccess={handleRefreshAll}
        />
      )}
      {showAeModal && (
        <ReportAdverseEventModal
          onClose={() => setShowAeModal(false)}
          onSuccess={handleRefreshAll}
        />
      )}
      {showDeviationModal && (
        <LogProtocolDeviationModal
          onClose={() => setShowDeviationModal(false)}
          onSuccess={handleRefreshAll}
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
