// Clinical Research Coordinator: the person who actually books the visits and
// enters the data. Their screen is a worklist, not a report - it answers "what
// do I have to do this week", so both tables are worth the full width.

import { useEffect, useState } from 'react'
import { fetchTrials } from '../api'
import DashboardLayout from './layout'

function SiteIECStatusBanner() {
  const [trial, setTrial] = useState(null)

  useEffect(() => {
    fetchTrials()
      .then((res) => {
        if (res.items?.[0]) setTrial(res.items[0])
      })
      .catch(() => {})
  }, [])

  const isApproved = trial?.ethics_approval_status === 'approved'

  return (
    <div className={`flex items-center justify-between rounded-lg border px-4 py-2.5 text-xs ${
      isApproved
        ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
        : 'border-amber-200 bg-amber-50 text-amber-900'
    }`}>
      <span className="flex items-center gap-2 font-medium">
        <span className={`flex h-2 w-2 rounded-full ${isApproved ? 'bg-emerald-600' : 'bg-amber-600'}`}></span>
        {isApproved
          ? `✅ IEC Clearance Active (${trial.ethics_approval_number || 'Approved'}): Site authorized to screen & enroll participants.`
          : `⚠️ Enrollment On Hold: Trial ethics approval is ${trial?.ethics_approval_status || 'Pending'}. Software blocks enrollment until IEC approves.`}
      </span>
      <span className="hidden sm:inline font-mono text-[11px]">
        NDCT Rules 2019 Rule 22
      </span>
    </div>
  )
}

export default function Coordinator(props) {
  return (
    <div className="space-y-4">
      <SiteIECStatusBanner />
      <DashboardLayout
        {...props}
        wide={['upcoming', 'screening']}
        simulateFirst
        note="Your worklist for the next two weeks. An overdue visit becomes a protocol deviation if it slips outside its window, so these dates are the ones that matter."
      />
    </div>
  )
}
