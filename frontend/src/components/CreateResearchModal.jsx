import { useState } from 'react'
import { createTrial } from '../api'
import { useAuth } from '../auth'

export default function CreateResearchModal({ onClose, onSuccess }) {
  const { user } = useAuth()
  const [protocolNumber, setProtocolNumber] = useState('')
  const [title, setTitle] = useState('')
  const [shortTitle, setShortTitle] = useState('')
  const [phase, setPhase] = useState('phase_3')
  const [indication, setIndication] = useState('')
  const [indicationAyurveda, setIndicationAyurveda] = useState('')
  const [intervention, setIntervention] = useState('')
  const [comparator, setComparator] = useState('')
  const [design, setDesign] = useState('Multicentre, Randomised, Double-Blind, Parallel-Group')
  const [sponsorName, setSponsorName] = useState(
    user?.organization || 'All India Institute of Ayurveda (AIIA), Ministry of Ayush'
  )
  const [targetEnrollment, setTargetEnrollment] = useState(100)
  const [startDate, setStartDate] = useState(new Date().toISOString().slice(0, 10))
  const [plannedEndDate, setPlannedEndDate] = useState(() => {
    const d = new Date()
    d.setFullYear(d.getFullYear() + 1)
    return d.toISOString().slice(0, 10)
  })

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [successMsg, setSuccessMsg] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setSuccessMsg(null)

    const payload = {
      protocol_number: protocolNumber.trim().toUpperCase(),
      title: title.trim(),
      short_title: shortTitle.trim() || title.trim().slice(0, 180),
      phase,
      indication: indication.trim(),
      indication_ayurveda: indicationAyurveda.trim() || null,
      intervention: intervention.trim(),
      comparator: comparator.trim() || null,
      design: design.trim(),
      sponsor_name: sponsorName.trim(),
      target_enrollment: Number(targetEnrollment) || 100,
      start_date: startDate || null,
      planned_end_date: plannedEndDate || null,
    }

    try {
      const res = await createTrial(payload)
      setSuccessMsg(`Research protocol ${res.protocol_number} created successfully! Initialized in Planning status pending Ethics review.`)
      setTimeout(() => {
        onSuccess?.(res)
        onClose()
      }, 1500)
    } catch (err) {
      setError(err?.detail || err?.message || 'Failed to register clinical trial protocol')
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-lg bg-white shadow-2xl border border-slate-300">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 bg-slate-100 px-6 py-4">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded bg-indigo-900 text-xs font-bold text-white">
              +
            </span>
            <div>
              <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wide">
                Register New Clinical Research Protocol
              </h2>
              <p className="text-xs text-slate-500">
                Institutional Research Creation under NDCT Rules 2019 &amp; ICH GCP E6(R2)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded border border-slate-300 bg-white px-3 py-1 text-xs font-bold text-slate-600 hover:bg-slate-200"
          >
            ✕
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* Institutional Scoping Banner */}
          <div className="rounded border border-indigo-200 bg-indigo-50/70 p-3 text-xs text-indigo-900">
            <span className="font-bold">Institutional Affiliation: </span>
            {user?.organization || 'National Central Registry'} &bull; Creator:{' '}
            <span className="font-semibold">{user?.full_name} ({user?.role_label || user?.role})</span>
            <p className="mt-1 text-[11px] text-indigo-700">
              This study protocol will automatically provision an initial research site bound to your assigned medical institute.
            </p>
          </div>

          {error && (
            <div className="rounded border border-red-200 bg-red-50 p-3 text-xs text-red-800">
              <strong>Error:</strong> {error}
            </div>
          )}

          {successMsg && (
            <div className="rounded border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800 font-semibold">
              ✅ {successMsg}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            {/* Protocol Number */}
            <div>
              <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">
                Protocol Number / Code *
              </label>
              <input
                type="text"
                required
                value={protocolNumber}
                onChange={(e) => setProtocolNumber(e.target.value.toUpperCase())}
                placeholder="e.g. AIIA-BRAHMI-2026-01"
                className="w-full rounded border border-slate-300 px-3 py-2 text-xs font-mono font-bold text-slate-800 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
              />
            </div>

            {/* Trial Phase */}
            <div>
              <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">
                Study Phase *
              </label>
              <select
                value={phase}
                onChange={(e) => setPhase(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-xs font-medium text-slate-800 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
              >
                <option value="phase_1">Phase I (Safety &amp; Dosage)</option>
                <option value="phase_2">Phase II (Efficacy Exploration)</option>
                <option value="phase_3">Phase III (Confirmatory Double-Blind)</option>
                <option value="phase_4">Phase IV (Post-Marketing / Pharmacovigilance)</option>
              </select>
            </div>

            {/* Title */}
            <div className="sm:col-span-2">
              <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">
                Full Scientific Title *
              </label>
              <textarea
                required
                rows={2}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. A Multi-Centre, Randomised, Double-Blind, Placebo-Controlled Study to Evaluate the Efficacy and Safety of..."
                className="w-full rounded border border-slate-300 px-3 py-2 text-xs text-slate-800 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
              />
            </div>

            {/* Short Title */}
            <div>
              <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">
                Short / Public Title
              </label>
              <input
                type="text"
                value={shortTitle}
                onChange={(e) => setShortTitle(e.target.value)}
                placeholder="e.g. BRAHMI-MEM Trial"
                className="w-full rounded border border-slate-300 px-3 py-2 text-xs text-slate-800 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
              />
            </div>

            {/* Target Enrollment */}
            <div>
              <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">
                Target Enrollment (Subjects) *
              </label>
              <input
                type="number"
                required
                min={1}
                max={50000}
                value={targetEnrollment}
                onChange={(e) => setTargetEnrollment(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-xs font-bold text-slate-800 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
              />
            </div>

            {/* Indication Biomedical */}
            <div>
              <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">
                Clinical Indication (Biomedical) *
              </label>
              <input
                type="text"
                required
                value={indication}
                onChange={(e) => setIndication(e.target.value)}
                placeholder="e.g. Mild Cognitive Impairment (MCI)"
                className="w-full rounded border border-slate-300 px-3 py-2 text-xs text-slate-800 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
              />
            </div>

            {/* Indication Ayurveda */}
            <div>
              <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">
                Ayurvedic Indication / Roga
              </label>
              <input
                type="text"
                value={indicationAyurveda}
                onChange={(e) => setIndicationAyurveda(e.target.value)}
                placeholder="e.g. Smriti Daurbalya / Manasa Roga"
                className="w-full rounded border border-slate-300 px-3 py-2 text-xs text-slate-800 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
              />
            </div>

            {/* Intervention */}
            <div>
              <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">
                Study Intervention / Formulation *
              </label>
              <input
                type="text"
                required
                value={intervention}
                onChange={(e) => setIntervention(e.target.value)}
                placeholder="e.g. Brahmi Ghrita 10g BD with warm milk"
                className="w-full rounded border border-slate-300 px-3 py-2 text-xs text-slate-800 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
              />
            </div>

            {/* Comparator */}
            <div>
              <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">
                Comparator / Control Arm
              </label>
              <input
                type="text"
                value={comparator}
                onChange={(e) => setComparator(e.target.value)}
                placeholder="e.g. Matched Placebo Ghrita"
                className="w-full rounded border border-slate-300 px-3 py-2 text-xs text-slate-800 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
              />
            </div>

            {/* Study Design */}
            <div>
              <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">
                Study Design
              </label>
              <input
                type="text"
                value={design}
                onChange={(e) => setDesign(e.target.value)}
                placeholder="e.g. Multicentre, Randomised, Double-Blind, Parallel-Group"
                className="w-full rounded border border-slate-300 px-3 py-2 text-xs text-slate-800 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
              />
            </div>

            {/* Sponsor Name */}
            <div>
              <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">
                Sponsor / Funder Entity *
              </label>
              <input
                type="text"
                required
                value={sponsorName}
                onChange={(e) => setSponsorName(e.target.value)}
                placeholder="e.g. Ministry of Ayush / AIIA Research Fund"
                className="w-full rounded border border-slate-300 px-3 py-2 text-xs text-slate-800 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
              />
            </div>

            {/* Dates */}
            <div>
              <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">
                Planned Start Date
              </label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-xs text-slate-800 focus:border-indigo-600 focus:outline-none"
              />
            </div>

            <div>
              <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">
                Planned Completion Date
              </label>
              <input
                type="date"
                value={plannedEndDate}
                onChange={(e) => setPlannedEndDate(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-xs text-slate-800 focus:border-indigo-600 focus:outline-none"
              />
            </div>
          </div>

          {/* Regulatory Note */}
          <div className="rounded border border-amber-200 bg-amber-50 p-3 text-[11px] text-amber-900 leading-relaxed">
            <strong>NDCT Rules 2019 Notice:</strong> Registered protocols initialize in <em>Planning (Pending Ethics)</em>.
            Before participant recruitment or screening can begin, the protocol must be formally reviewed and approved by the Institutional Ethics Committee (IEC) and prospective registration completed on CTRI.
          </div>

          {/* Footer Actions */}
          <div className="flex justify-end gap-3 pt-4 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="rounded border border-slate-300 bg-white px-4 py-2 text-xs font-bold text-slate-700 hover:bg-slate-100 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy}
              className="rounded bg-indigo-900 px-5 py-2 text-xs font-bold text-white shadow-sm hover:bg-indigo-800 disabled:opacity-50 flex items-center gap-1.5"
            >
              {busy ? 'Registering Protocol...' : 'Register Clinical Protocol'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
