import { useState } from 'react'
import DashboardLayout from './layout'
import { api } from '../api'

export default function DSMB(props) {
  const [decision, setDecision] = useState('CONTINUE')
  const [error, setError] = useState(null)

  const logDecision = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      await api('/api/trials/1/dsmb-decision', {
        method: 'PATCH',
        body: {
          decision: decision,
          notes: "Routine quarterly safety review."
        }
      })
      alert(`Decision to ${decision} officially logged in audit trail.`)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <div className="mb-8 p-6 bg-white border border-slate-200 rounded-xl shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Trial Continuation Decision Logger</h2>
        <form onSubmit={logDecision} className="bg-slate-50 p-4 rounded-lg border border-slate-200">
          <p className="text-sm text-slate-600 mb-4">Based on the aggregate safety analytics, please log your board&apos;s official decision.</p>
          {error && <div className="mb-4 text-red-600 text-sm">{error}</div>}
          <div className="flex gap-6 mb-6">
            <label className="flex items-center gap-2 text-sm font-medium">
              <input type="radio" name="decision" value="CONTINUE" checked={decision === 'CONTINUE'} onChange={e => setDecision(e.target.value)} />
              Continue Trial
            </label>
            <label className="flex items-center gap-2 text-sm font-medium">
              <input type="radio" name="decision" value="MODIFY" checked={decision === 'MODIFY'} onChange={e => setDecision(e.target.value)} />
              Modify Protocol
            </label>
            <label className="flex items-center gap-2 text-sm font-medium text-red-700">
              <input type="radio" name="decision" value="HALT" checked={decision === 'HALT'} onChange={e => setDecision(e.target.value)} />
              Halt Trial (Emergency)
            </label>
          </div>
          <button type="submit" className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700">
            Submit Official Decision
          </button>
        </form>
      </div>

      <DashboardLayout {...props} />
    </div>
  )
}
