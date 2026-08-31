// Principal Investigator: the doctor legally responsible for the trial at one
// hospital. Everything on this screen is their own site - asking for another
// site's participant returns 403, by design.

import { useEffect, useState } from 'react'
import { fetchTrials } from '../api'
import DashboardLayout from './layout'

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
  return (
    <div className="space-y-4">
      <SiteComplianceStatusBanner />
      <DashboardLayout
        {...props}
        wide={['recent_aes']}
        simulateFirst
        note="Scoped to your site only. Safety first: an open adverse event is one that has not resolved yet, and a serious one has to reach the ethics committee within days."
      />
    </div>
  )
}
