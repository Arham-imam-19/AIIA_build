import { useState } from 'react'
import { submitSaeEthicsDecision } from '../api'

export default function SaeEthicsReviewModal({ sae, onClose, onSuccess }) {
  const [decision, setDecision] = useState(sae.ec_decision || 'accepted')
  const [notes, setNotes] = useState(sae.ec_decision_notes || '')
  const [decisionDate, setDecisionDate] = useState(
    sae.ec_decision_date || new Date().toISOString().slice(0, 10)
  )
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')

    try {
      await submitSaeEthicsDecision(sae.id, {
        decision,
        notes: notes.trim(),
        decision_date: decisionDate,
      })
      onSuccess?.()
    } catch (err) {
      setError(err?.message || 'Failed to submit IEC adjudication')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col rounded-none border-2 border-slate-700 bg-white shadow-2xl overflow-hidden">
        {/* Government Style Header */}
        <div className="border-b-2 border-slate-700 bg-slate-800 text-white px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">⚖️</span>
            <div>
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-100">
                Institutional Ethics Committee &bull; Formal Safety Adjudication
              </h2>
              <p className="text-xs text-slate-300 font-mono">
                SAE Docket: {sae.ae_number} &bull; Participant: {sae.subject_code} &bull; Site: [{sae.site_code}] {sae.site_name}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-300 hover:text-white text-lg font-bold px-2 py-1"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {error && (
            <div className="rounded-none border border-rose-500 bg-rose-50 p-3 text-xs text-rose-800 font-medium">
              <strong>Submission Error:</strong> {error}
            </div>
          )}

          {/* Clinical Event Dossier Box */}
          <div className="rounded-none border border-slate-300 bg-slate-50 p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-200 pb-2">
              <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                Clinical Safety Event Summary
              </span>
              <span className={`px-2 py-0.5 text-xs font-semibold uppercase ${
                sae.clock_status === 'OVERDUE'
                  ? 'bg-rose-100 text-rose-800 border border-rose-300'
                  : 'bg-emerald-100 text-emerald-800 border border-emerald-300'
              }`}>
                24h Clock: {sae.clock_label}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div>
                <span className="text-slate-500 block text-[11px]">Verbatim Term:</span>
                <span className="font-bold text-slate-900">{sae.term_verbatim}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[11px]">Seriousness Criteria:</span>
                <span className="font-semibold text-rose-700">{sae.seriousness_criteria}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[11px]">Severity / Causality:</span>
                <span className="font-medium text-slate-800 uppercase">{sae.severity} / {sae.causality}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[11px]">Onset Date:</span>
                <span className="font-mono text-slate-800">{sae.onset_date}</span>
              </div>
            </div>

            {sae.description && (
              <div className="pt-2 border-t border-slate-200">
                <span className="text-slate-500 block text-[11px] mb-1">Clinical Narrative / Investigator Notes:</span>
                <p className="text-xs text-slate-700 bg-white p-2.5 border border-slate-200 font-mono leading-relaxed">
                  {sae.description}
                </p>
              </div>
            )}
          </div>

          {/* Committee Ruling Form */}
          <form id="iec-adjudication-form" onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-800 mb-1">
                Ethics Committee Formal Ruling
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <label className={`flex items-center gap-2 p-3 border-2 cursor-pointer transition ${
                  decision === 'accepted'
                    ? 'border-emerald-600 bg-emerald-50 text-emerald-950 font-bold'
                    : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400'
                }`}>
                  <input
                    type="radio"
                    name="decision"
                    value="accepted"
                    checked={decision === 'accepted'}
                    onChange={(e) => setDecision(e.target.value)}
                    className="h-4 w-4 text-emerald-600"
                  />
                  <span className="text-xs">
                    ✅ Accept / Clear (Continue Protocol)
                  </span>
                </label>

                <label className={`flex items-center gap-2 p-3 border-2 cursor-pointer transition ${
                  decision === 'rejected'
                    ? 'border-rose-600 bg-rose-50 text-rose-950 font-bold'
                    : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400'
                }`}>
                  <input
                    type="radio"
                    name="decision"
                    value="rejected"
                    checked={decision === 'rejected'}
                    onChange={(e) => setDecision(e.target.value)}
                    className="h-4 w-4 text-rose-600"
                  />
                  <span className="text-xs">
                    ❌ Reject / Halt Trial Medication
                  </span>
                </label>

                <label className={`flex items-center gap-2 p-3 border-2 cursor-pointer transition ${
                  decision === 'action_required'
                    ? 'border-amber-600 bg-amber-50 text-amber-950 font-bold'
                    : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400'
                }`}>
                  <input
                    type="radio"
                    name="decision"
                    value="action_required"
                    checked={decision === 'action_required'}
                    onChange={(e) => setDecision(e.target.value)}
                    className="h-4 w-4 text-amber-600"
                  />
                  <span className="text-xs">
                    ⚠️ Action Required / Investigator Query
                  </span>
                </label>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Adjudication Date
                </label>
                <input
                  type="date"
                  required
                  value={decisionDate}
                  onChange={(e) => setDecisionDate(e.target.value)}
                  className="w-full rounded-none border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-900 focus:border-slate-600 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Regulatory Mandate Ref
                </label>
                <input
                  type="text"
                  disabled
                  value="NDCT Rules 2019 Rule 42 & Schedule Y GCP"
                  className="w-full rounded-none border border-slate-200 bg-slate-100 px-3 py-1.5 text-xs text-slate-600 cursor-not-allowed"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Official Committee Directives & Review Notes <span className="text-slate-400 font-normal">(Visible to PI and Study Coordinator)</span>
              </label>
              <textarea
                rows={3}
                required={decision === 'rejected' || decision === 'action_required'}
                placeholder="e.g. Safety evaluation cleared. Unblinded data indicates event is non-intervention related. Continued surveillance ordered."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full rounded-none border border-slate-300 bg-white p-3 text-xs text-slate-900 placeholder-slate-400 focus:border-slate-600 focus:outline-none font-mono"
              />
            </div>
          </form>
        </div>

        {/* Government Style Footer */}
        <div className="border-t-2 border-slate-700 bg-slate-100 px-6 py-3.5 flex items-center justify-between text-xs">
          <span className="text-slate-600 font-mono text-[11px]">
            Institutional Ethics Committee Adjudication Record &bull; SHA-256 Hash Chained
          </span>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-none border border-slate-400 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition"
            >
              Cancel
            </button>
            <button
              form="iec-adjudication-form"
              type="submit"
              disabled={submitting}
              className="rounded-none bg-slate-900 px-5 py-2 text-xs font-bold text-white hover:bg-slate-800 transition disabled:opacity-50"
            >
              {submitting ? 'Recording Adjudication...' : '⚖️ Record Official Ruling & Transmit to PI'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
