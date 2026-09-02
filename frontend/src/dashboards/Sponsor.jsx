import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'

export default function Sponsor(props) {
  const { dashboard } = props
  const { user } = useAuth()
  const [metrics, setMetrics] = useState(null)
  const [selectedSite, setSelectedSite] = useState('All')
  
  useEffect(() => {
    api('/api/sponsor/dashboard-metrics').then(setMetrics).catch(console.error)
  }, [])

  if (!metrics) {
    return <div className="p-8 text-center text-slate-500">Loading sponsor metrics...</div>
  }

  const isGlobal = user?.access_scope === 'GLOBAL'

  // Mock cost metrics based on enrolled patients
  const costPerPatient = metrics.total_enrolled > 0 ? Math.floor(18500000 / metrics.total_enrolled) : 0;

  return (
    <div className="space-y-6">
      {/* Dashboard Header */}
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-base font-semibold tracking-tight text-slate-900">
            {dashboard.title}
          </h2>
          <p className="text-sm text-slate-500">{dashboard.subtitle}</p>
          <p className="mt-1.5 text-xs leading-relaxed text-slate-400">
            Sponsor view: Medical Trust Blue theme active.
          </p>
        </div>

        {/* Top Right Filters */}
        <div className="flex gap-3">
          <select 
            value={selectedSite} 
            onChange={e => setSelectedSite(e.target.value)}
            className="border border-slate-300 rounded-lg px-4 py-2 text-sm text-slate-700 bg-white font-medium shadow-sm hover:border-aiia-400 focus:outline-none focus:ring-2 focus:ring-aiia-500"
          >
            <option value="All">Filter by Site: All Hospitals</option>
            <option value="Delhi">All India Institute of Ayurveda, New Delhi</option>
            <option value="Jaipur">National Institute of Ayurveda, Jaipur</option>
            <option value="Kolkata">National Research Institute, Kolkata</option>
            <option value="Jamnagar">ITRA, Jamnagar</option>
          </select>

          {isGlobal && (
            <select className="border border-slate-300 rounded-lg px-4 py-2 text-sm text-slate-700 bg-white font-medium shadow-sm hover:border-aiia-400 focus:outline-none focus:ring-2 focus:ring-aiia-500">
              <option>Filter by Funder: All</option>
              <option>Himalaya Wellness</option>
            </select>
          )}
        </div>
      </div>

      {/* Privacy Lock Banner */}
      <div className="bg-slate-800 text-white px-4 py-3 rounded-lg shadow-sm flex items-center gap-3">
        <span>🔒</span>
        <span className="text-sm font-medium">
          Data Privacy Lock active: Patient identifiers are fully redacted from this view.
        </span>
      </div>

      {/* Top KPI Cards */}
      <div className="flex gap-4">
        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex-1">
          <div className="text-xs uppercase font-bold tracking-wider text-slate-500 mb-1">Total Active Trials</div>
          <div className="text-3xl font-bold text-slate-900">{metrics.total_active_trials}</div>
        </div>
        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex-1">
          <div className="text-xs uppercase font-bold tracking-wider text-slate-500 mb-1">Total Enrolled vs Target</div>
          <div className="flex items-end gap-2">
            <div className="text-3xl font-bold text-aiia-600">{metrics.total_enrolled}</div>
            <div className="text-sm font-medium text-slate-400 mb-1">/ {metrics.target_enrollment}</div>
          </div>
          <div className="w-full bg-slate-100 h-1.5 mt-3 rounded-full overflow-hidden">
            <div 
              className="bg-aiia-500 h-full" 
              style={{ width: `${Math.min(100, (metrics.total_enrolled / metrics.target_enrollment) * 100)}%` }}
            ></div>
          </div>
        </div>
        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex-1">
          <div className="text-xs uppercase font-bold tracking-wider text-slate-500 mb-1">Budget Burn Rate</div>
          <div className="text-3xl font-bold text-red-600">{metrics.budget_burn_rate}%</div>
          <div className="text-xs text-red-600 font-medium mt-1">↑ Expected based on visits</div>
        </div>
      </div>

      {/* Secondary Metrics */}
      <div className="flex gap-4">
        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex-1">
          <div className="text-xs uppercase font-bold tracking-wider text-slate-500 mb-1">Screening Success Rate</div>
          <div className="text-2xl font-bold text-slate-900">{metrics.screening_success_rate}%</div>
        </div>
        
        <div className="bg-white border border-red-200 p-4 rounded-xl shadow-sm flex-1">
          <div className="text-xs uppercase font-bold tracking-wider text-red-600 mb-1">Financial Leakage</div>
          <div className="text-2xl font-bold text-slate-900">₹{metrics.estimated_failure_cost.toLocaleString()}</div>
          <div className="text-xs text-slate-500 mt-1">Cost of {metrics.total_screen_failed} screen failures</div>
        </div>
        
        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex-1">
          <div className="text-xs uppercase font-bold tracking-wider text-slate-500 mb-1">Cost per Enrolled Patient</div>
          <div className="text-2xl font-bold text-aiia-600">₹{costPerPatient.toLocaleString()}</div>
          <div className="text-xs text-slate-500 mt-1">Total spend / {metrics.total_enrolled} enrolled</div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex-1">
          <div className="text-xs uppercase font-bold tracking-wider text-slate-500 mb-1">Serious Events (SAEs)</div>
          <div className="text-2xl font-bold text-slate-900">{metrics.serious_events}</div>
          <div className="text-xs text-slate-500 mt-1">Across all sites</div>
        </div>
      </div>
      
      {/* Site Activation Funnel */}
      <div className="bg-white border border-slate-200 p-5 rounded-xl shadow-sm">
        <div className="flex justify-between items-center mb-4">
            <div className="text-sm font-bold text-slate-900">Site Activation Status</div>
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">CRA Performance: {metrics.cra_performance.open_queries} Open Queries, {metrics.cra_performance.overdue_visits} Overdue Visits</div>
        </div>
        <div className="flex gap-2">
          <div className="flex-1 bg-green-50 text-green-700 p-3 rounded text-center border border-green-100">
            <div className="text-2xl font-bold">{metrics.site_activation.recruiting}</div>
            <div className="text-xs uppercase tracking-wider font-semibold">Recruiting</div>
          </div>
          <div className="flex-1 bg-amber-50 text-amber-700 p-3 rounded text-center border border-amber-100">
            <div className="text-2xl font-bold">{metrics.site_activation.awaiting_ethics}</div>
            <div className="text-xs uppercase tracking-wider font-semibold">Awaiting Ethics</div>
          </div>
          <div className="flex-1 bg-slate-50 text-slate-600 p-3 rounded text-center border border-slate-100">
            <div className="text-2xl font-bold">{metrics.site_activation.contract_pending}</div>
            <div className="text-xs uppercase tracking-wider font-semibold">Contract Pending</div>
          </div>
        </div>
      </div>
    </div>
  )
}
