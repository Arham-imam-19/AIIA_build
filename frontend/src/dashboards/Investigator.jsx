// Principal Investigator: the doctor legally responsible for the trial at one
// hospital. Everything on this screen is their own site - asking for another
// site's participant returns 403, by design.

import { useState } from 'react'
import DashboardLayout from './layout'
import { api } from '../api'

export default function Investigator(props) {
  const [saeModal, setSaeModal] = useState(false)
  const [subjectId, setSubjectId] = useState(1)
  const [term, setTerm] = useState('')
  const [error, setError] = useState(null)

  const reportSAE = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      await api('/api/adverse-events', {
        method: 'POST',
        body: {
          subject_id: subjectId,
          term_verbatim: term,
          severity: 'severe',
          is_serious: true,
          seriousness_criteria: 'hospitalization',
          causality: 'probable',
          action_taken: 'drug_withdrawn',
          outcome: 'ongoing'
        }
      })
      setSaeModal(false)
      setTerm('')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <div className="flex gap-4 mb-6">
        <button onClick={() => alert("Add Patient (Mock): Sending e-Consent SMS to patient...")} className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium shadow-sm hover:bg-blue-700">
          + Add Patient
        </button>
        <button onClick={() => alert("EDC Form (Mock): Logging daily BP and Prakriti observations...")} className="bg-white text-slate-700 border border-slate-300 px-4 py-2 rounded-lg text-sm font-medium shadow-sm hover:bg-slate-50">
          📝 Log EDC Vitals
        </button>
        <button onClick={() => setSaeModal(true)} className="bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-medium shadow-sm hover:bg-red-700 ml-auto flex items-center gap-2">
          🚨 Report Severe Adverse Event (SAE)
        </button>
      </div>

      {saeModal && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50">
          <form onSubmit={reportSAE} className="bg-white p-6 rounded-xl shadow-xl max-w-md w-full">
            <h3 className="text-lg font-bold text-slate-900 mb-4">Report Severe Adverse Event</h3>

            {error && <div className="mb-4 text-red-600 text-sm bg-red-50 p-2 rounded">{error}</div>}

            <label className="block text-sm font-medium text-slate-700 mb-1">Subject ID (Internal)</label>
            <input type="number" value={subjectId} onChange={e => setSubjectId(Number(e.target.value))} className="w-full border border-slate-300 rounded p-2 mb-4 text-sm" />

            <label className="block text-sm font-medium text-slate-700 mb-1">Event Term</label>
            <input type="text" value={term} onChange={e => setTerm(e.target.value)} placeholder="e.g. Severe Nausea" className="w-full border border-slate-300 rounded p-2 mb-6 text-sm" required />

            <div className="flex justify-end gap-3">
              <button type="button" onClick={() => setSaeModal(false)} className="px-4 py-2 text-sm text-slate-600 font-medium hover:bg-slate-50 rounded">Cancel</button>
              <button type="submit" className="px-4 py-2 text-sm bg-red-600 text-white font-medium rounded hover:bg-red-700">Submit to PV</button>
            </div>
          </form>
        </div>
      )}

      <DashboardLayout
        {...props}
        wide={['recent_aes']}
        note="Scoped to your site only. Safety first: an open adverse event is one that has not resolved yet, and a serious one has to reach the ethics committee within days."
      />
    </div>
  )
}
