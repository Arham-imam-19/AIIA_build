import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import DashboardLayout from './layout'
import DataExportCenter from '../components/DataExportCenter'

export default function Sponsor(props) {
  const { dashboard } = props
  const { user } = useAuth()
  const [metrics, setMetrics] = useState(null)
  const [selectedSite, setSelectedSite] = useState('All')

  useEffect(() => {
    api('/api/sponsor/dashboard-metrics')
      .then(setMetrics)
      .catch((err) => {
        console.error('Failed to load sponsor dashboard metrics:', err)
      })
  }, [])

  const isGlobal = user?.access_scope === 'GLOBAL'
  const costPerPatient =
    metrics && metrics.total_enrolled > 0
      ? Math.floor(18500000 / metrics.total_enrolled)
      : 0

  return (
    <div className="space-y-6">
      {/* Official Government DPDP Act 2023 / Blinding Oversight Banner */}
      <div className="flex items-center justify-between border border-blue-200 bg-blue-50/80 px-4 py-3 text-xs text-blue-900 shadow-sm">
        <span className="flex items-center gap-2 font-medium">
          <span className="flex h-2.5 w-2.5 rounded-full bg-blue-600"></span>
          🔒 DPDP Act 2023 &amp; ICH GCP: Blinded Sponsor Oversight Mode
        </span>
        <span className="text-blue-700 hidden sm:inline text-[11px]">
          Individual participant PII and randomization arm allocations are server-blinded to maintain trial integrity.
        </span>
      </div>

      {/* Top KPI Cards (if metrics available) */}
      {metrics && (
        <>
          <div className="flex flex-wrap gap-4">
            <div className="bg-white border border-slate-200 p-4 rounded shadow-sm flex-1 min-w-[200px]">
              <div className="text-xs uppercase font-bold tracking-wider text-slate-500 mb-1">Total Active Trials</div>
              <div className="text-3xl font-bold text-slate-900">{metrics.total_active_trials}</div>
            </div>
            <div className="bg-white border border-slate-200 p-4 rounded shadow-sm flex-1 min-w-[200px]">
              <div className="text-xs uppercase font-bold tracking-wider text-slate-500 mb-1">Total Enrolled vs Target</div>
              <div className="flex items-end gap-2">
                <div className="text-3xl font-bold text-indigo-700">{metrics.total_enrolled}</div>
                <div className="text-sm font-medium text-slate-400 mb-1">/ {metrics.target_enrollment}</div>
              </div>
              <div className="w-full bg-slate-100 h-1.5 mt-3 rounded-full overflow-hidden">
                <div
                  className="bg-indigo-600 h-full transition-all"
                  style={{ width: `${Math.min(100, (metrics.total_enrolled / (metrics.target_enrollment || 1)) * 100)}%` }}
                ></div>
              </div>
            </div>
            <div className="bg-white border border-slate-200 p-4 rounded shadow-sm flex-1 min-w-[200px]">
              <div className="text-xs uppercase font-bold tracking-wider text-slate-500 mb-1">Budget Burn Rate</div>
              <div className="text-3xl font-bold text-red-600">{metrics.budget_burn_rate}%</div>
              <div className="text-xs text-slate-500 font-medium mt-1">↑ Expected based on visit milestone pace</div>
            </div>
          </div>

          {/* Secondary Financial & Safety Metrics */}
          <div className="flex flex-wrap gap-4">
            <div className="bg-white border border-slate-200 p-4 rounded shadow-sm flex-1 min-w-[180px]">
              <div className="text-xs uppercase font-bold tracking-wider text-slate-500 mb-1">Screening Success</div>
              <div className="text-2xl font-bold text-slate-900">{metrics.screening_success_rate}%</div>
            </div>
            <div className="bg-white border border-red-200 p-4 rounded shadow-sm flex-1 min-w-[180px]">
              <div className="text-xs uppercase font-bold tracking-wider text-red-600 mb-1">Financial Leakage</div>
              <div className="text-2xl font-bold text-slate-900">₹{metrics.estimated_failure_cost.toLocaleString()}</div>
              <div className="text-xs text-slate-500 mt-1">Cost of {metrics.total_screen_failed} screen failures</div>
            </div>
            <div className="bg-white border border-slate-200 p-4 rounded shadow-sm flex-1 min-w-[180px]">
              <div className="text-xs uppercase font-bold tracking-wider text-slate-500 mb-1">Cost / Enrolled Subject</div>
              <div className="text-2xl font-bold text-indigo-700">₹{costPerPatient.toLocaleString()}</div>
              <div className="text-xs text-slate-500 mt-1">Milestone burn / {metrics.total_enrolled} enrolled</div>
            </div>
            <div className="bg-white border border-slate-200 p-4 rounded shadow-sm flex-1 min-w-[180px]">
              <div className="text-xs uppercase font-bold tracking-wider text-slate-500 mb-1">Serious Events (SAEs)</div>
              <div className="text-2xl font-bold text-slate-900">{metrics.serious_events}</div>
              <div className="text-xs text-slate-500 mt-1">Across all sites (24h clock)</div>
            </div>
          </div>

          {/* Site Activation Funnel */}
          <div className="bg-white border border-slate-200 p-5 rounded shadow-sm">
            <div className="flex flex-wrap justify-between items-center gap-2 mb-4">
              <div className="text-sm font-bold text-slate-900">Site Activation &amp; Compliance Status</div>
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                CRA Oversight: {metrics.cra_performance.open_queries} Open Queries &middot; {metrics.cra_performance.overdue_visits} Overdue Visits
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <div className="flex-1 min-w-[140px] bg-emerald-50 text-emerald-800 p-3 rounded text-center border border-emerald-200">
                <div className="text-2xl font-bold">{metrics.site_activation.recruiting}</div>
                <div className="text-xs uppercase tracking-wider font-semibold">Active Recruiting</div>
              </div>
              <div className="flex-1 min-w-[140px] bg-amber-50 text-amber-800 p-3 rounded text-center border border-amber-200">
                <div className="text-2xl font-bold">{metrics.site_activation.awaiting_ethics}</div>
                <div className="text-xs uppercase tracking-wider font-semibold">Awaiting Ethics</div>
              </div>
              <div className="flex-1 min-w-[140px] bg-slate-50 text-slate-700 p-3 rounded text-center border border-slate-200">
                <div className="text-2xl font-bold">{metrics.site_activation.contract_pending}</div>
                <div className="text-xs uppercase tracking-wider font-semibold">Contract Pending</div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Universal Data Export Center (CDISC SDTM Dataset-JSON & HL7 FHIR R4) */}
      <DataExportCenter />

      {/* Standard Site Performance Tables */}
      <DashboardLayout
        {...props}
        wide={['site_performance']}
        note="Every site, all sites. A Sponsor cannot enter or edit trial data: a monitor who could change the numbers would undermine the numbers. Leave this screen open and have the coordinator enrol someone - it moves on its own."
      />
    </div>
  )
}
