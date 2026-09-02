// Institution Administrator: manages hospital site operations, coordinates researchers,
// monitors local recruitment & safety, and reviews/responds to patient inquiries.

import { useState } from 'react'
import { respondPatientRequest } from '../api'
import DashboardLayout from './layout'
import DataExportCenter from '../components/DataExportCenter'

function RespondModal({ requestId, onClose, onSuccess }) {
  const [response, setResponse] = useState('')
  const [status, setStatus] = useState('resolved')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await respondPatientRequest(requestId, { response, status })
      onSuccess?.()
      onClose()
    } catch (err) {
      setError(err.detail || err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <h3 className="text-base font-semibold text-slate-900">
          Respond to Patient Inquiry #{requestId}
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          Your response will be recorded in the trial audit log and visible in the patient's portal.
        </p>

        {error && (
          <div className="mt-3 rounded-lg bg-red-50 p-3 text-xs text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-700">
              Response / Clinical Recommendation
            </label>
            <textarea
              required
              rows={4}
              value={response}
              onChange={(e) => setResponse(e.target.value)}
              placeholder="e.g. As discussed with Dr. Sharma (PI), please take the medication with warm milk after food..."
              className="mt-1 w-full rounded-lg border border-slate-200 p-2.5 text-sm text-slate-800 outline-none focus:border-aiia-500 focus:ring-1 focus:ring-aiia-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700">
              Update Request Status
            </label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2 text-sm text-slate-800 outline-none focus:border-aiia-500"
            >
              <option value="resolved">Resolved (Completed)</option>
              <option value="in_review">In Review (Awaiting Clinical Input)</option>
              <option value="escalated">Escalate to Ethics Committee / PI</option>
            </select>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-aiia-600 px-4 py-2 text-xs font-medium text-white hover:bg-aiia-700 disabled:opacity-50"
            >
              {busy ? 'Saving…' : 'Submit Response'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function InstitutionAdmin(props) {
  const [selectedRequest, setSelectedRequest] = useState(null)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between rounded-lg border border-teal-100 bg-teal-50/70 px-4 py-2.5 text-xs text-teal-900">
        <span className="flex items-center gap-2 font-medium">
          <span className="flex h-2 w-2 rounded-full bg-teal-600"></span>
          🏥 Site Healthcare Provider Scope: Direct Patient Communication Enabled
        </span>
        <span className="text-teal-700 hidden sm:inline">
          Access is limited to participants enrolled at your hospital site.
        </span>
      </div>

      <DashboardLayout
        {...props}
        wide={['patient_requests', 'staff']}
        note="Institution Scope: Manage hospital research personnel, track patient enrollment milestones, and respond to participant inquiries."
      />

      {/* Action button in dashboard context */}
      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-sm font-semibold text-slate-800">
              Patient Inquiry Management
            </h4>
            <p className="text-xs text-slate-500">
              Select an inquiry ID to draft an official response or change its review status.
            </p>
          </div>
          <button
            onClick={() => setSelectedRequest(1)}
            className="rounded-lg bg-aiia-600 px-3.5 py-2 text-xs font-medium text-white shadow-sm hover:bg-aiia-700"
          >
            Reply to Patient Inquiry
          </button>
        </div>
      </div>

      <DataExportCenter />

      {selectedRequest && (
        <RespondModal
          requestId={selectedRequest}
          onClose={() => setSelectedRequest(null)}
          onSuccess={props.onRefresh}
        />
      )}
    </div>
  )
}
