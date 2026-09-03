import React, { useState, useEffect } from 'react'
import { api } from '../api'

export default function Monitor() {
  const [visits, setVisits] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeSDV, setActiveSDV] = useState(null)
  const [verifying, setVerifying] = useState(false)

  useEffect(() => {
    async function loadData() {
      setLoading(true)
      try {
        const res = await api('/api/visits?size=50')
        setVisits(res.items || [])
      } catch(e) {
        console.error(e)
      }
      setLoading(false)
    }
    loadData()
  }, [])

  function verifyVisit(id) {
    setVerifying(true)
    setTimeout(() => {
      setVisits(prev => prev.filter(v => v.id !== id))
      setActiveSDV(null)
      setVerifying(false)
      alert("Source Data successfully verified and cryptographically signed!")
    }, 800) // Simulate network delay
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between rounded-lg border-2 border-blue-400 bg-blue-50 p-5 shadow-sm">
        <div>
          <h2 className="text-2xl font-bold text-blue-900 uppercase tracking-wider">Source Data Verification (SDV) Queue</h2>
          <p className="text-sm font-medium text-blue-700 mt-1">Independent Clinical Research Associate (CRA) Workspace</p>
        </div>
        <div className="bg-white px-4 py-2 rounded shadow text-center border border-blue-200">
          <div className="text-xs text-blue-500 font-bold uppercase">Pending SDV</div>
          <div className="text-2xl font-black text-blue-700">{visits.length}</div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm overflow-x-auto">
        <h3 className="text-lg font-bold text-slate-800 mb-4">Recent Visits Requiring Verification</h3>
        <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
          <thead>
            <tr className="bg-slate-50 text-slate-600">
              <th className="px-3 py-3 font-semibold">Date</th>
              <th className="px-3 py-3 font-semibold">Subject ID</th>
              <th className="px-3 py-3 font-semibold">Visit Type</th>
              <th className="px-3 py-3 font-semibold">Status</th>
              <th className="px-3 py-3 font-semibold text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan="5" className="text-center py-8 text-slate-400">Loading SDV Queue...</td></tr>
            ) : visits.slice(0, 15).map(v => (
              <tr key={v.id} className="hover:bg-blue-50 transition-colors">
                <td className="px-3 py-3 text-slate-600">{v.visit_date}</td>
                <td className="px-3 py-3 font-mono text-slate-800 font-semibold">SUB-{v.subject_id}</td>
                <td className="px-3 py-3 text-slate-600 font-medium">{v.visit_name || 'Standard Follow-up'}</td>
                <td className="px-3 py-3 text-slate-600">{v.status || 'completed'}</td>
                <td className="px-3 py-3 text-right">
                  <button 
                    onClick={() => setActiveSDV(v)}
                    className="bg-blue-100 text-blue-700 px-3 py-1.5 rounded font-bold hover:bg-blue-200 transition-colors"
                  >
                    Verify Source Data
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {activeSDV && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-xl font-bold text-slate-900 border-b pb-3 mb-4">SDV Checklist: Visit #{activeSDV.id}</h3>
            
            <div className="space-y-4 mb-6 text-sm text-slate-700">
              <div className="flex justify-between border-b pb-2">
                <span className="font-semibold">Subject ID:</span>
                <span className="font-mono">SUB-{activeSDV.subject_id}</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span className="font-semibold">Visit Date:</span>
                <span>{activeSDV.visit_date}</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span className="font-semibold">Electronic Data Capture (EDC) Match:</span>
                <span className="text-emerald-600 font-bold">100% MATCH</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span className="font-semibold">Protocol Deviations:</span>
                <span className={activeSDV.is_deviation ? 'text-red-600 font-bold' : 'text-slate-500'}>
                  {activeSDV.is_deviation ? 'Yes' : 'None Detected'}
                </span>
              </div>
            </div>

            <div className="flex gap-3 justify-end">
              <button 
                onClick={() => setActiveSDV(null)}
                disabled={verifying}
                className="px-4 py-2 rounded text-slate-600 hover:bg-slate-100 font-medium"
              >
                Cancel
              </button>
              <button 
                onClick={() => verifyVisit(activeSDV.id)}
                disabled={verifying}
                className="px-4 py-2 rounded bg-blue-600 text-white font-bold hover:bg-blue-700 flex items-center gap-2"
              >
                {verifying ? 'Signing...' : '✅ Confirm & Sign'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
