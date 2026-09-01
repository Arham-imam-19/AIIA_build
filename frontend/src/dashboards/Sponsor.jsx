import DashboardLayout from './layout'

export default function Sponsor(props) {
  return (
    <div>
      <div className="flex gap-4 mb-6">
        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex-1">
          <div className="text-xs uppercase font-bold tracking-wider text-slate-500 mb-1">Total Active Trials</div>
          <div className="text-3xl font-bold text-slate-900">1</div>
        </div>
        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex-1">
          <div className="text-xs uppercase font-bold tracking-wider text-slate-500 mb-1">Total Enrolled vs Target</div>
          <div className="flex items-end gap-2">
            <div className="text-3xl font-bold text-aiia-600">186</div>
            <div className="text-sm font-medium text-slate-400 mb-1">/ 240</div>
          </div>
          <div className="w-full bg-slate-100 h-1.5 mt-3 rounded-full overflow-hidden">
            <div className="bg-aiia-500 h-full w-[77%]"></div>
          </div>
        </div>
        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex-1">
          <div className="text-xs uppercase font-bold tracking-wider text-slate-500 mb-1">Budget Burn Rate</div>
          <div className="text-3xl font-bold text-red-600">62.4%</div>
          <div className="text-xs text-red-600 font-medium mt-1">↑ 4.1% this month</div>
        </div>
      </div>
      
      <DashboardLayout
        {...props}
        wide={['site_performance']}
        note="Data Privacy Lock active: Patient identifiers are fully redacted from this view."
      />
    </div>
  )
}
