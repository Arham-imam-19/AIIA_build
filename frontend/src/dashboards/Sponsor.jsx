// Sponsor: funds and oversees the study but never touches the data. The question
// is always the same - is this trial on track, across every site?

import DashboardLayout from './layout'

export default function Sponsor(props) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between rounded-lg border border-blue-100 bg-blue-50/70 px-4 py-2.5 text-xs text-blue-900">
        <span className="flex items-center gap-2 font-medium">
          <span className="flex h-2 w-2 rounded-full bg-blue-600"></span>
          🔒 DPDP Act 2023: Blinded Sponsor Oversight Mode
        </span>
        <span className="text-blue-700 hidden sm:inline">
          Individual participant PII is masked to prevent observer bias and protect patient privacy.
        </span>
      </div>

      <DashboardLayout
        {...props}
        wide={['site_performance']}
        note="Every site, all sites. A Sponsor cannot enter or edit trial data: a monitor who could change the numbers would undermine the numbers. Leave this screen open and have the coordinator enrol someone - it moves on its own."
      />
    </div>
  )
}
