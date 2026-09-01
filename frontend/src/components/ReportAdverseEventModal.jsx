import { useEffect, useState } from 'react'
import { createAdverseEvent, fetchSubjects } from '../api'

const COMMON_MEDDRA_TERMS = [
  { term: 'Epigastric discomfort', code: '10015037', soc: 'Gastrointestinal disorders' },
  { term: 'Gastritis', code: '10017853', soc: 'Gastrointestinal disorders' },
  { term: 'Nausea', code: '10028813', soc: 'Gastrointestinal disorders' },
  { term: 'Headache', code: '10019211', soc: 'Nervous system disorders' },
  { term: 'Dizziness', code: '10013573', soc: 'Nervous system disorders' },
  { term: 'Insomnia', code: '10022437', soc: 'Psychiatric disorders' },
  { term: 'Pruritus / Skin Rash', code: '10037087', soc: 'Skin and subcutaneous tissue disorders' },
  { term: 'Alanine aminotransferase increased', code: '10001551', soc: 'Investigations' },
  { term: 'Fatigue', code: '10016256', soc: 'General disorders and administration site conditions' },
]

export default function ReportAdverseEventModal({ trialId = 1, onClose, onSuccess }) {
  const [subjects, setSubjects] = useState([])
  const [subjectId, setSubjectId] = useState('')
  const [termVerbatim, setTermVerbatim] = useState('')
  const [description, setDescription] = useState('')
  const [onsetDate, setOnsetDate] = useState(new Date().toISOString().split('T')[0])
  const [severity, setSeverity] = useState('mild')
  const [isSerious, setIsSerious] = useState(false)
  const [seriousnessCriteria, setSeriousnessCriteria] = useState('Hospitalization')
  const [causality, setCausality] = useState('possible')
  const [outcome, setOutcome] = useState('recovering')
  const [actionTaken, setActionTaken] = useState('Dose not changed')
  const [meddraIndex, setMeddraIndex] = useState(0)
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

    const selectedMeddra = COMMON_MEDDRA_TERMS[meddraIndex]

    try {
      await createAdverseEvent({
        trial_id: Number(trialId),
        subject_id: Number(subjectId),
        term_verbatim: termVerbatim.trim() || selectedMeddra.term,
        description: description.trim() || undefined,
        onset_date: onsetDate,
        severity,
        is_serious: isSerious,
        seriousness_criteria: isSerious ? seriousnessCriteria : undefined,
        causality,
        outcome,
        action_taken: actionTaken,
        meddra_pt_code: selectedMeddra.code,
        meddra_pt_term: selectedMeddra.term,
        meddra_soc: selectedMeddra.soc,
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
              🚨 Structured Adverse Event Safety Report (ICH E2A / CIOMS)
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              MedDRA Dictionary Coding & NDCT Rules 2019 Regulatory Clocks
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
                    {sub.subject_code} ({sub.status?.toUpperCase()} • {sub.arm || 'No Arm'})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Onset Date
              </label>
              <input
                type="date"
                max={new Date().toISOString().split('T')[0]}
                value={onsetDate}
                onChange={(e) => setOnsetDate(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Reported Symptoms / Verbatim Term
              </label>
              <input
                type="text"
                value={termVerbatim}
                onChange={(e) => setTermVerbatim(e.target.value)}
                placeholder="e.g. Severe burning epigastric discomfort"
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                required
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                MedDRA Dictionary Coding (PT & SOC)
              </label>
              <select
                value={meddraIndex}
                onChange={(e) => setMeddraIndex(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs font-medium text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                {COMMON_MEDDRA_TERMS.map((m, idx) => (
                  <option key={m.code} value={idx}>
                    {m.term} ({m.soc})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block font-medium text-slate-700 dark:text-slate-300">
              Clinical Narrative / Description
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe clinical course, diagnostic tests, and doctor evaluation..."
              className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Severity (CTCAE)
              </label>
              <select
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs font-medium text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                <option value="mild">Mild (Grade 1)</option>
                <option value="moderate">Moderate (Grade 2)</option>
                <option value="severe">Severe (Grade 3)</option>
              </select>
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Causality / Relatedness
              </label>
              <select
                value={causality}
                onChange={(e) => setCausality(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs font-medium text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                <option value="definite">Definite / Certain</option>
                <option value="probable">Probable</option>
                <option value="possible">Possible</option>
                <option value="unlikely">Unlikely</option>
                <option value="unrelated">Unrelated</option>
              </select>
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Clinical Outcome
              </label>
              <select
                value={outcome}
                onChange={(e) => setOutcome(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs font-medium text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                <option value="recovering">Recovering / Resolving</option>
                <option value="recovered">Recovered / Resolved</option>
                <option value="not_recovered">Not Recovered</option>
                <option value="fatal">Fatal</option>
              </select>
            </div>
          </div>

          {/* Seriousness Section */}
          <div className="rounded-xl border border-red-200 bg-red-50/50 p-3.5 dark:border-red-900/50 dark:bg-red-950/30">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_serious"
                checked={isSerious}
                onChange={(e) => setIsSerious(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-red-600 focus:ring-red-500"
              />
              <label htmlFor="is_serious" className="font-bold text-xs text-red-900 dark:text-red-200">
                Mark as Serious Adverse Event (SAE) — Triggers 24-Hour Expedited Regulatory Clock
              </label>
            </div>

            {isSerious && (
              <div className="mt-2.5 pl-6">
                <label className="block text-[11px] font-medium text-red-800 dark:text-red-300">
                  Statutory Seriousness Criterion (ICH E2A / NDCT Rules)
                </label>
                <select
                  value={seriousnessCriteria}
                  onChange={(e) => setSeriousnessCriteria(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-red-200 p-2 text-xs font-medium text-red-900 dark:border-red-800 dark:bg-slate-900 dark:text-red-200"
                >
                  <option value="Hospitalization">Requires Inpatient Hospitalization / Prolongation</option>
                  <option value="Life-threatening">Life-Threatening Incident</option>
                  <option value="Disability">Persistent or Significant Disability/Incapacity</option>
                  <option value="Congenital Anomaly">Congenital Anomaly / Birth Defect</option>
                  <option value="Death">Death / Fatal Event</option>
                  <option value="Important Medical Event">Important Medical Event</option>
                </select>
              </div>
            )}
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
              className="rounded-lg bg-red-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-red-700 disabled:opacity-50"
            >
              {busy ? 'Reporting...' : isSerious ? '🚨 Submit Serious Adverse Event (SAE)' : 'Submit Adverse Event'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
