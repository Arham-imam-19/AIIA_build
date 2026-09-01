import DashboardLayout from './layout'

export default function Coordinator(props) {
  return (
    <div>
      <div className="flex gap-4 mb-6">
        <div className="bg-white border border-slate-200 text-slate-700 px-4 py-3 rounded-xl shadow-sm flex items-center gap-3 w-1/3">
          <span className="text-2xl">📅</span>
          <div>
            <div className="text-sm font-bold uppercase tracking-wider text-slate-900">Visit Calendar</div>
            <div className="text-xs">3 patients due for Week-2 checkup today.</div>
          </div>
        </div>
        <div className="bg-white border border-slate-200 text-slate-700 px-4 py-3 rounded-xl shadow-sm flex items-center gap-3 w-1/3">
          <span className="text-2xl">📋</span>
          <div>
            <div className="text-sm font-bold uppercase tracking-wider text-slate-900">Task Inbox</div>
            <div className="text-xs text-amber-600 font-medium">2 overdue data entry tasks.</div>
          </div>
        </div>
        <div className="bg-white border border-dashed border-slate-300 text-slate-500 px-4 py-3 rounded-xl flex items-center justify-center gap-3 w-1/3 cursor-pointer hover:bg-slate-50" onClick={() => alert("Mock: Uploaded Source Document (e.g. PDF Lab Results)")}>
          <span className="text-xl">📄</span>
          <div className="text-sm font-medium">Drag & Drop Source Documents (PDF/Images)</div>
        </div>
      </div>

      <DashboardLayout
        {...props}
        wide={['upcoming', 'screening']}
        simulateFirst
        note="Your worklist for the next two weeks. An overdue visit becomes a protocol deviation if it slips outside its window, so these dates are the ones that matter."
      />
    </div>
  )
}
