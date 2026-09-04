import { useState } from 'react'
import DashboardLayout from './layout'
import { api } from '../api'

export default function Monitor(props) {
  const [queryModal, setQueryModal] = useState(false)
  const [queryText, setQueryText] = useState('')
  const [visitId, setVisitId] = useState(1)
  const [error, setError] = useState(null)

  const raiseQuery = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      await api(`/api/visits/${visitId}/query`, {
        method: 'PATCH',
        body: { query_text: queryText }
      })
      setQueryModal(false)
      setQueryText('')
      alert("Query successfully raised. Email dispatched to PI.")
    } catch (err) {
      setError(err.message)
    }
  }

  const handleVerify = () => {
    alert("Source Data Verification (SDV) successfully completed. Record locked.")
  }

  return (
    <div className="space-y-6">

      <div className="mb-6">
        <h2 className="text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">
          Monitor
        </h2>
        <p className="text-sm text-slate-500">Monitor &bull; All participating sites</p>
      </div>

      
      {/* KPI Header */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-amber-700">Source Data Verification</div>
            <div className="mt-1 text-2xl font-semibold text-amber-900 tabular-nums">PENDING SDV: 50</div>
            <div className="mt-1 text-xs text-amber-700 font-medium">CRF pages require monitor review</div>
          </div>
          <div className="h-12 w-12 rounded-full bg-amber-100 flex items-center justify-center text-amber-600">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
          </div>
        </div>

        <div className="rounded-xl border border-red-200 bg-red-50 p-5 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-red-700">Issue Management</div>
            <div className="mt-1 text-2xl font-semibold text-red-900 tabular-nums">OPEN QUERIES: 14</div>
            <div className="mt-1 text-xs text-red-700 font-medium">Awaiting site coordinator resolution</div>
          </div>
          <div className="h-12 w-12 rounded-full bg-red-100 flex items-center justify-center text-red-600">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
          </div>
        </div>
      </div>

      <div className="p-6 bg-white border border-slate-200 rounded-xl shadow-sm">
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-slate-900 uppercase tracking-wide text-xs">INDEPENDENT MONITOR WORKSPACE - Source Data Verification (SDV) Queue</h2>
          <p className="text-xs text-slate-500 mt-0.5">Recent Visits Requiring Verification from assigned sites.</p>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600 border-collapse">
            <thead className="bg-slate-50 text-xs uppercase font-bold tracking-wider text-slate-500 border-b border-slate-200">
              <tr>
                <th className="px-4 py-3 border-r border-slate-200">Date</th>
                <th className="px-4 py-3 border-r border-slate-200">Site / Hospital</th>
                <th className="px-4 py-3 border-r border-slate-200">Subject</th>
                <th className="px-4 py-3 border-r border-slate-200">Visit</th>
                <th className="px-4 py-3 border-r border-slate-200">Reported Value</th>
                <th className="px-4 py-3 border-r border-slate-200">Status</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              <tr className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-slate-500 border-r border-slate-100">2026-09-02</td>
                <td className="px-4 py-3 border-r border-slate-100 font-medium text-slate-800">AIIA New Delhi</td>
                <td className="px-4 py-3 font-mono text-slate-700 border-r border-slate-100">SUB-014</td>
                <td className="px-4 py-3 border-r border-slate-100">Week 4 Vitals</td>
                <td className="px-4 py-3 border-r border-slate-100 font-mono">Systolic BP: 800 mmHg</td>
                <td className="px-4 py-3 border-r border-slate-100">
                  <span className="px-2 py-1 bg-amber-50 text-amber-700 border border-amber-200 rounded font-bold uppercase tracking-wider text-[10px]">Pending SDV</span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <button onClick={handleVerify} className="border border-emerald-600 text-emerald-700 hover:bg-emerald-50 px-3 py-1.5 rounded font-semibold text-[10px] uppercase tracking-wider transition-colors">
                      Verify (SDV)
                    </button>
                    <button onClick={() => setQueryModal(true)} className="border border-red-600 text-red-700 hover:bg-red-50 px-3 py-1.5 rounded font-semibold text-[10px] uppercase tracking-wider transition-colors">
                      Raise Query
                    </button>
                  </div>
                </td>
              </tr>
              <tr className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-slate-500 border-r border-slate-100">2026-09-03</td>
                <td className="px-4 py-3 border-r border-slate-100 font-medium text-slate-800">NIA Jaipur</td>
                <td className="px-4 py-3 font-mono text-slate-700 border-r border-slate-100">SUB-045</td>
                <td className="px-4 py-3 border-r border-slate-100">Screening Log</td>
                <td className="px-4 py-3 border-r border-slate-100 font-mono">Informed Consent: Yes</td>
                <td className="px-4 py-3 border-r border-slate-100">
                  <span className="px-2 py-1 bg-amber-50 text-amber-700 border border-amber-200 rounded font-bold uppercase tracking-wider text-[10px]">Pending SDV</span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <button onClick={handleVerify} className="border border-emerald-600 text-emerald-700 hover:bg-emerald-50 px-3 py-1.5 rounded font-semibold text-[10px] uppercase tracking-wider transition-colors">
                      Verify (SDV)
                    </button>
                    <button onClick={() => setQueryModal(true)} className="border border-red-600 text-red-700 hover:bg-red-50 px-3 py-1.5 rounded font-semibold text-[10px] uppercase tracking-wider transition-colors">
                      Raise Query
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {queryModal && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
          <form onSubmit={raiseQuery} className="bg-white p-6 shadow-xl max-w-md w-full border border-slate-300">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 mb-4 border-b border-slate-200 pb-3">Raise Data Query to Site</h3>
            {error && <div className="mb-4 text-red-800 text-xs bg-red-50 p-3 font-medium border border-red-200">{error}</div>}

            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">Message to Investigator / CRC</label>
            <textarea value={queryText} onChange={e => setQueryText(e.target.value)} placeholder="Please verify this value against source paper records. The reported BP of 800 mmHg is physiologically impossible..." className="w-full border border-slate-300 bg-slate-50 p-3 mb-6 text-sm h-32 focus:outline-none focus:border-slate-800" required />

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-200">
              <button type="button" onClick={() => setQueryModal(false)} className="border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors">Cancel</button>
              <button type="submit" className="border border-red-700 bg-red-600 px-4 py-2 text-xs font-bold uppercase tracking-wider text-white hover:bg-red-700 transition-colors">Open Query</button>
            </div>
          </form>
        </div>
      )}

      {/* Hide default sponsor layout so our custom CRA UI takes focus */}
      <div className="opacity-50 pointer-events-none mt-12">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-4 px-2">Global Sponsor Fallback Dashboard</h3>
        <DashboardLayout {...props} />
      </div>
    </div>
  )
}
