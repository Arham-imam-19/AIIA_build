import { useState } from 'react'
import DashboardLayout from './layout'
import { api } from '../api'

export default function Pharmacovigilance(props) {
  const [meddraModal, setMeddraModal] = useState(false)
  const [eventId, setEventId] = useState(1)
  const [pt, setPt] = useState('Nausea')
  const [error, setError] = useState(null)

  const codeMeddra = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      await api(`/api/adverse-events/${eventId}/meddra`, {
        method: 'PATCH',
        body: {
          meddra_llt: pt,
          meddra_llt_code: "10028813",
          meddra_pt: pt,
          meddra_pt_code: "10028813",
          meddra_soc: "Gastrointestinal disorders",
          meddra_soc_code: "10017947"
        }
      })
      setMeddraModal(false)
      alert("Event coded successfully in MedDRA dictionary.")
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <div className="flex gap-4 mb-6">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl shadow-sm flex items-center gap-3">
          <span className="text-2xl">⏳</span>
          <div>
            <div className="text-sm font-bold uppercase tracking-wider">NDCT 2019 Regulatory Timer</div>
            <div className="text-xs">14h 23m remaining to report SAE-01-014 to CDSCO.</div>
          </div>
        </div>
      </div>

      <div className="mb-8 p-6 bg-white border border-slate-200 rounded-xl shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">AE Triage Inbox</h2>
        <table className="w-full text-left text-sm text-slate-600">
          <thead className="bg-slate-50 text-xs uppercase font-medium text-slate-500">
            <tr>
              <th className="px-4 py-3">Event ID</th>
              <th className="px-4 py-3">Reported Term</th>
              <th className="px-4 py-3">MedDRA Code</th>
              <th className="px-4 py-3">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            <tr>
              <td className="px-4 py-3 font-mono">AE-01-014-01</td>
              <td className="px-4 py-3">&quot;Patient threw up&quot;</td>
              <td className="px-4 py-3"><span className="px-2 py-1 bg-slate-100 text-slate-600 rounded-full text-xs font-medium">Uncoded</span></td>
              <td className="px-4 py-3">
                <button onClick={() => setMeddraModal(true)} className="text-aiia-600 hover:text-aiia-700 font-medium">Code (MedDRA)</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {meddraModal && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50">
          <form onSubmit={codeMeddra} className="bg-white p-6 rounded-xl shadow-xl max-w-md w-full">
            <h3 className="text-lg font-bold text-slate-900 mb-4">MedDRA Dictionary Coding</h3>
            {error && <div className="mb-4 text-red-600 text-sm bg-red-50 p-2 rounded">{error}</div>}

            <label className="block text-sm font-medium text-slate-700 mb-1">Select Preferred Term (PT)</label>
            <select value={pt} onChange={e => setPt(e.target.value)} className="w-full border border-slate-300 rounded p-2 mb-6 text-sm">
              <option value="Nausea">Nausea (10028813)</option>
              <option value="Vomiting">Vomiting (10047700)</option>
              <option value="Headache">Headache (10019211)</option>
            </select>

            <div className="flex justify-end gap-3">
              <button type="button" onClick={() => setMeddraModal(false)} className="px-4 py-2 text-sm text-slate-600 font-medium hover:bg-slate-50 rounded">Cancel</button>
              <button type="submit" className="px-4 py-2 text-sm bg-blue-600 text-white font-medium rounded hover:bg-blue-700">Apply Code</button>
            </div>
          </form>
        </div>
      )}

      <DashboardLayout {...props} />
    </div>
  )
}
