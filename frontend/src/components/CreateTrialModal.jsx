import { useState } from 'react'
import { createTrial } from '../api'

export default function CreateTrialModal({ onClose, onSuccess }) {
  const [protocolNumber, setProtocolNumber] = useState('AIIA-NEO-2026-02')
  const [title, setTitle] = useState('')
  const [shortTitle, setShortTitle] = useState('')
  const [phase, setPhase] = useState('phase_2')
  const [indication, setIndication] = useState('')
  const [indicationAyurveda, setIndicationAyurveda] = useState('')
  const [intervention, setIntervention] = useState('')
  const [comparator, setComparator] = useState('')
  const [design, setDesign] = useState('Randomized, Double-Blind, Parallel-Group Trial')
  const [sponsorName, setSponsorName] = useState('All India Institute of Ayurveda (AIIA)')
  const [targetEnrollment, setTargetEnrollment] = useState(100)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await createTrial({
        protocol_number: protocolNumber.trim().toUpperCase(),
        title: title.trim(),
        short_title: shortTitle.trim() || undefined,
        phase,
        indication: indication.trim(),
        indication_ayurveda: indicationAyurveda.trim() || undefined,
        intervention: intervention.trim(),
        comparator: comparator.trim() || undefined,
        design: design.trim(),
        sponsor_name: sponsorName.trim(),
        target_enrollment: Number(targetEnrollment),
      })
      onSuccess?.()
      onClose()
    } catch (err) {
      setError(err.detail || err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 dark:border-slate-800">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              📜 Define & Provision Clinical Trial Protocol
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              ICH GCP E6(R2), CDISC TS Domain & Indian CTRI Compliant Setup
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="mt-3 rounded-lg bg-red-50 p-3 text-xs font-medium text-red-700 dark:bg-red-950 dark:text-red-300">
            {typeof error === 'string' ? error : JSON.stringify(error)}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Protocol Number
              </label>
              <input
                type="text"
                required
                value={protocolNumber}
                onChange={(e) => setProtocolNumber(e.target.value)}
                placeholder="e.g. AIIA-ASH-2026-02"
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs font-mono font-bold text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Trial Phase
              </label>
              <select
                value={phase}
                onChange={(e) => setPhase(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs font-medium text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                <option value="phase_1">Phase I (Safety & Pharmacokinetics)</option>
                <option value="phase_2">Phase II (Therapeutic Exploratory / Dose-Ranging)</option>
                <option value="phase_3">Phase III (Confirmatory Multi-Centric Efficacy)</option>
                <option value="phase_4">Phase IV (Post-Marketing Surveillance / Real-World)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block font-medium text-slate-700 dark:text-slate-300">
              Full Scientific Study Title
            </label>
            <textarea
              required
              rows={2}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. A Multi-Centric, Randomized, Double-Blind Active-Controlled Clinical Trial Evaluating Efficacy and Safety of..."
              className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Biomedical Indication
              </label>
              <input
                type="text"
                required
                value={indication}
                onChange={(e) => setIndication(e.target.value)}
                placeholder="e.g. Type 2 Diabetes Mellitus"
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Ayurvedic Indication (NAMASTE / ICD-11 TM2)
              </label>
              <input
                type="text"
                value={indicationAyurveda}
                onChange={(e) => setIndicationAyurveda(e.target.value)}
                placeholder="e.g. Madhumeha / Prameha"
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Investigational Product (IP) / Formulation
              </label>
              <input
                type="text"
                required
                value={intervention}
                onChange={(e) => setIntervention(e.target.value)}
                placeholder="e.g. Nisha-Amalaki Ghanavati 500mg TID"
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Comparator / Control Arm
              </label>
              <input
                type="text"
                value={comparator}
                onChange={(e) => setComparator(e.target.value)}
                placeholder="e.g. Standard Care Metformin 500mg"
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Target Sample Size
              </label>
              <input
                type="number"
                required
                min={10}
                max={5000}
                value={targetEnrollment}
                onChange={(e) => setTargetEnrollment(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
            <div className="col-span-2">
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Sponsor / Lead Institution
              </label>
              <input
                type="text"
                required
                value={sponsorName}
                onChange={(e) => setSponsorName(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
          </div>

          <div className="rounded-xl border border-blue-100 bg-blue-50/70 p-3 text-[11px] text-blue-900 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-200">
            ⚖️ <strong>Regulatory Sequence Gate Notice:</strong> Upon creation, trial will sit in <code>PLANNING</code> status. It will require Institutional Ethics Committee (IEC) approval and prospective CTRI registration before site recruitment can activate.
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-aiia-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-aiia-700 disabled:opacity-50"
            >
              {busy ? 'Creating Protocol...' : 'Create Trial Protocol'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
