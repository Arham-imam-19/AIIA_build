import { useEffect, useState } from 'react'
import { fetchSubjects, logProtocolDeviation } from '../api'

const DEVIATION_CATEGORIES = [
  'VISIT WINDOW EXCEEDED (±7 Days)',
  'INFORMED CONSENT DEVIATION',
  'INCLUSION / EXCLUSION CRITERIA NON-COMPLIANCE',
  'PROHIBITED CONCOMITANT MEDICATION TAKEN',
  'INVESTIGATIONAL PRODUCT DOSING / COMPLIANCE',
  'MISSED LABORATORY / SAFETY ASSESSMENT',
  'OTHER PROTOCOL SPECIFICATION DEVIATION',
]

export default function LogProtocolDeviationModal({ trialId = 1, onClose, onSuccess }) {
  const [subjects, setSubjects] = useState([])
  const [subjectId, setSubjectId] = useState('')
  const [category, setCategory] = useState(DEVIATION_CATEGORIES[0])
  const [description, setDescription] = useState('')
  const [clinicalImpact, setClinicalImpact] = useState('No direct impact on participant safety or study endpoints')
  const [capa, setCapa] = useState('')
  const [deviationDate, setDeviationDate] = useState(new Date().toISOString().split('T')[0])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchSubjects({ limit: 50 })
      .then((res) => {
        if (res.items?.length) {
          setSubjects(res.items)
          setSubjectId(res.items[0].id)
        }
      })
      .catch(() => {})
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!subjectId) return
    setBusy(true)
    setError(null)

    try {
      await logProtocolDeviation({
        trial_id: Number(trialId),
        subject_id: Number(subjectId),
        category,
        description: description.trim(),
        clinical_impact: clinicalImpact.trim() || undefined,
        capa: capa.trim() || undefined,
        deviation_date: deviationDate,
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
      <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 dark:border-slate-800">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              ⚠️ Log Protocol Deviation & CAPA
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              ICH E6(R2) & CDISC DV Domain Statutory Recording
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
                Participant Selection
              </label>
              <select
                value={subjectId}
                onChange={(e) => setSubjectId(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs font-medium text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                required
              >
                {subjects.map((sub) => (
                  <option key={sub.id} value={sub.id}>
                    {sub.subject_code} ({sub.status?.toUpperCase()})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Date of Occurrence
              </label>
              <input
                type="date"
                max={new Date().toISOString().split('T')[0]}
                value={deviationDate}
                onChange={(e) => setDeviationDate(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                required
              />
            </div>
          </div>

          <div>
            <label className="block font-medium text-slate-700 dark:text-slate-300">
              Standard Deviation Category (CDISC DV Domain)
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs font-medium text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            >
              {DEVIATION_CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block font-medium text-slate-700 dark:text-slate-300">
              Deviation Description & Narrative
            </label>
            <textarea
              required
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Patient attended Visit 3 eight days outside the permissible protocol window due to out-of-station travel..."
              className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            />
          </div>

          <div>
            <label className="block font-medium text-slate-700 dark:text-slate-300">
              Clinical & Safety Impact Assessment
            </label>
            <input
              type="text"
              value={clinicalImpact}
              onChange={(e) => setClinicalImpact(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            />
          </div>

          <div>
            <label className="block font-medium text-slate-700 dark:text-slate-300">
              Corrective and Preventive Action (CAPA)
            </label>
            <textarea
              rows={2}
              value={capa}
              onChange={(e) => setCapa(e.target.value)}
              placeholder="e.g. Automated appointment reminder SMS scheduled 48 hours prior to upcoming window..."
              className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            />
          </div>

          <div className="rounded-lg bg-amber-50/70 p-2.5 text-[11px] text-amber-900 dark:bg-amber-950/60 dark:text-amber-300">
            ⚖️ <strong>Ethics Committee Notice:</strong> This deviation record and CAPA will immediately appear on the Institutional Ethics Committee (IEC) review queue.
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
              className="rounded-lg bg-amber-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-amber-700 disabled:opacity-50"
            >
              {busy ? 'Logging...' : 'Log Deviation & CAPA'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
