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

  return (
    <div>
      <div className="mb-8 p-6 bg-white border border-slate-200 rounded-xl shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Source Data Verification (SDV)</h2>
        <table className="w-full text-left text-sm text-slate-600">
          <thead className="bg-slate-50 text-xs uppercase font-medium text-slate-500">
            <tr>
              <th className="px-4 py-3">Subject</th>
              <th className="px-4 py-3">Visit</th>
              <th className="px-4 py-3">Reported Value</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            <tr>
              <td className="px-4 py-3 font-mono">01-014</td>
              <td className="px-4 py-3">Week 4 Vitals</td>
              <td className="px-4 py-3">Systolic BP: 800 mmHg</td>
              <td className="px-4 py-3"><span className="px-2 py-1 bg-amber-50 text-amber-700 rounded-full text-xs font-medium">Pending SDV</span></td>
              <td className="px-4 py-3">
                <button onClick={() => setQueryModal(true)} className="text-aiia-600 hover:text-aiia-700 font-medium">Raise Query</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {queryModal && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50">
          <form onSubmit={raiseQuery} className="bg-white p-6 rounded-xl shadow-xl max-w-md w-full">
            <h3 className="text-lg font-bold text-slate-900 mb-4">Raise Data Query</h3>
            {error && <div className="mb-4 text-red-600 text-sm bg-red-50 p-2 rounded">{error}</div>}

            <label className="block text-sm font-medium text-slate-700 mb-1">Message to Investigator</label>
            <textarea value={queryText} onChange={e => setQueryText(e.target.value)} placeholder="Please verify this value against source paper records..." className="w-full border border-slate-300 rounded p-2 mb-6 text-sm h-24" required />

            <div className="flex justify-end gap-3">
              <button type="button" onClick={() => setQueryModal(false)} className="px-4 py-2 text-sm text-slate-600 font-medium hover:bg-slate-50 rounded">Cancel</button>
              <button type="submit" className="px-4 py-2 text-sm bg-amber-600 text-white font-medium rounded hover:bg-amber-700">Open Query</button>
            </div>
          </form>
        </div>
      )}

      <DashboardLayout {...props} />
    </div>
  )
}
