import React, { useEffect, useState } from 'react'
import {
  fetchSubjectDossier,
  fetchSubjectClinicalLogs,
  appendSubjectClinicalLog,
} from '../api'
import { useAuth } from '../auth'

export default function PatientDetailPage({ subjectId, onBack, onRefresh }) {
  const { user } = useAuth()

  const [dossier, setDossier] = useState(null)
  const [clinicalLogs, setClinicalLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Add-entry state
  const [entryType, setEntryType] = useState('medication_administered')
  const [substanceName, setSubstanceName] = useState('Ashwagandha Root Extract (Standardized 5% Withanolides)')
  const [dose, setDose] = useState('500 mg BD')
  const [route, setRoute] = useState('Oral (Post-prandial)')
  const [observationDescription, setObservationDescription] = useState('')
  const [linkedVisitId, setLinkedVisitId] = useState('')
  const [isSerious, setIsSerious] = useState(false)
  const [aeSeverity, setAeSeverity] = useState('mild')

  // ALCOA+ Correction state
  const [isCorrection, setIsCorrection] = useState(false)
  const [correctionOfEntryId, setCorrectionOfEntryId] = useState('')
  const [correctionReason, setCorrectionReason] = useState('')

  // Form submission
  const [submitting, setSubmitting] = useState(false)
  const [submitSuccess, setSubmitSuccess] = useState(null)
  const [submitError, setSubmitError] = useState(null)

  async function loadData() {
    if (!subjectId) {
      setError('No participant selected.')
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const [dosData, logsData] = await Promise.all([
        fetchSubjectDossier(subjectId),
        fetchSubjectClinicalLogs(subjectId).catch(() => []),
      ])
      setDossier(dosData)
      setClinicalLogs(Array.isArray(logsData) ? logsData : [])
    } catch (err) {
      setError(err.detail || err.message || 'Failed to load participant data.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [subjectId])

  async function handleAddLogSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setSubmitError(null)
    setSubmitSuccess(null)

    if (!observationDescription.trim()) {
      setSubmitError('Clinical narrative/observation description is mandatory.')
      setSubmitting(false)
      return
    }

    if (isCorrection && !correctionReason.trim()) {
      setSubmitError('ALCOA+ Requirement: A documented reason for clinical record correction must be provided.')
      setSubmitting(false)
      return
    }

    try {
      const payload = {
        entry_type: entryType,
        substance_name: entryType === 'medication_administered' ? substanceName.trim() : null,
        dose: entryType === 'medication_administered' ? dose.trim() : null,
        route: entryType === 'medication_administered' ? route.trim() : null,
        observation_description: observationDescription.trim(),
        linked_visit_id: linkedVisitId ? Number(linkedVisitId) : null,
        correction_of_entry_id: isCorrection && correctionOfEntryId ? Number(correctionOfEntryId) : null,
        correction_reason: isCorrection ? correctionReason.trim() : null,
        is_serious: entryType === 'adverse_event' ? isSerious : false,
        ae_severity: entryType === 'adverse_event' ? aeSeverity : 'mild',
      }

      await appendSubjectClinicalLog(subjectId, payload)
      setSubmitSuccess('Clinical progress entry successfully appended to permanent trial ledger.')
      setObservationDescription('')
      setIsCorrection(false)
      setCorrectionOfEntryId('')
      setCorrectionReason('')
      if (entryType === 'adverse_event') {
        setIsSerious(false)
        setAeSeverity('mild')
      }

      // Refresh clinical logs and parent dashboard
      const updatedLogs = await fetchSubjectClinicalLogs(subjectId)
      setClinicalLogs(updatedLogs || [])
      onRefresh?.()
    } catch (err) {
      setSubmitError(err.detail || err.message || 'Failed to commit clinical progress log entry.')
    } finally {
      setSubmitting(false)
    }
  }

  function handleStartCorrection(entry) {
    setIsCorrection(true)
    setCorrectionOfEntryId(entry.id)
    setCorrectionReason('')
    setEntryType(entry.entry_type)
    if (entry.substance_name) setSubstanceName(entry.substance_name)
    if (entry.dose) setDose(entry.dose)
    if (entry.route) setRoute(entry.route)
    setObservationDescription(`[Correction of Entry #${entry.id}]: `)
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
  }

  if (loading) {
    return (
      <div className="border border-slate-300 bg-white p-8 text-center text-xs text-slate-500 shadow-sm">
        Retrieving clinical dossier and progress log for Subject #{subjectId}...
      </div>
    )
  }

  if (error || !dossier) {
    return (
      <div className="border border-red-300 bg-red-50 p-6 text-xs text-red-900 shadow-sm space-y-3">
        <div className="font-bold uppercase tracking-wider">Access or Loading Error:</div>
        <div>{error || 'Unable to retrieve participant details.'}</div>
        <button
          onClick={onBack}
          className="border border-slate-700 bg-white px-3 py-1.5 text-xs font-semibold uppercase text-slate-800 hover:bg-slate-100"
        >
          &larr; Return to Participants List
        </button>
      </div>
    )
  }

  const profile = dossier.profile || {}
  const consent = profile.consent || {}
  const visits = dossier.visits || []

  return (
    <div className="space-y-6">
      {/* Top Header & Breadcrumb */}
      <div className="border border-slate-300 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="border border-slate-300 bg-slate-100 px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-slate-700">
                Patient Detail & Clinical Log
              </span>
              <span className="font-mono text-xs font-semibold text-slate-500">
                {profile.site_name} (Site {profile.site_id}) &middot; Protocol {profile.protocol_number}
              </span>
            </div>
            <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 uppercase font-mono flex items-center gap-3">
              {profile.subject_code}
              <span className="text-xs font-sans font-bold uppercase border border-slate-300 bg-slate-50 px-2.5 py-0.5 text-slate-800">
                Status: {profile.status}
              </span>
              <span className="text-xs font-sans font-bold uppercase border border-blue-300 bg-blue-50 px-2.5 py-0.5 text-blue-800">
                Arm: {profile.arm}
              </span>
            </h1>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={onBack}
              className="border border-slate-400 bg-white px-4 py-2 text-xs font-bold uppercase tracking-wider text-slate-800 hover:bg-slate-100 transition"
            >
              &larr; Back to Directory
            </button>
          </div>
        </div>

        {/* ALCOA+ Audit Governance Notice */}
        <div className="mt-3 flex items-start gap-2.5 border-l-4 border-slate-700 bg-slate-50 p-3 text-xs text-slate-700">
          <div className="font-bold text-slate-900 uppercase tracking-wider text-[11px] whitespace-nowrap">
            ALCOA+ Governance:
          </div>
          <div className="leading-relaxed text-[11px]">
            Clinical logs are <strong>strictly append-only</strong>. Past entries cannot be edited or deleted. Errata must be submitted as new addenda referencing the original log ID. All timestamps and session author attributions are permanently sealed server-side under <strong>21 CFR Part 11 & GCP-ASU</strong> guidelines.
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* PART 1: READ VIEW (Subject's Existing Record Captured at Enrollment)      */}
      {/* ========================================================================= */}
      <div className="border border-slate-300 bg-white p-5 shadow-sm space-y-5">
        <div className="flex items-center justify-between border-b border-slate-200 pb-2.5">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900">
            Part 1: Participant Baseline & Enrollment Record (Read View)
          </h2>
          <span className="border border-slate-300 bg-slate-100 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase text-slate-600">
            Baseline Metadata &middot; Read-Only
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
          {/* Box 1: Lifecycle & Enrolment */}
          <div className="border border-slate-200 bg-slate-50 p-3.5 space-y-2">
            <div className="font-bold uppercase tracking-wider text-slate-700 border-b border-slate-200 pb-1 text-[11px]">
              Enrollment & Timeline
            </div>
            <div>
              <span className="block text-[10px] uppercase text-slate-500">Screening Date:</span>
              <span className="font-mono font-semibold text-slate-800">{profile.screening_date || '—'}</span>
            </div>
            <div>
              <span className="block text-[10px] uppercase text-slate-500">Enrollment Date:</span>
              <span className="font-mono font-semibold text-slate-800">{profile.enrollment_date || 'Pending formal enrollment'}</span>
            </div>
            <div>
              <span className="block text-[10px] uppercase text-slate-500">Randomization Date:</span>
              <span className="font-mono font-semibold text-slate-800">{profile.randomization_date || 'Not yet randomized'}</span>
            </div>
          </div>

          {/* Box 2: Demographics & Measures */}
          <div className="border border-slate-200 bg-slate-50 p-3.5 space-y-2">
            <div className="font-bold uppercase tracking-wider text-slate-700 border-b border-slate-200 pb-1 text-[11px]">
              Demographics & Biometrics
            </div>
            <div>
              <span className="block text-[10px] uppercase text-slate-500">Biological Sex:</span>
              <span className="font-semibold capitalize text-slate-800">{profile.sex}</span>
            </div>
            <div>
              <span className="block text-[10px] uppercase text-slate-500">Age & Year of Birth:</span>
              <span className="font-semibold text-slate-800">
                {profile.age ? `${profile.age} years` : '—'} {profile.year_of_birth && `(YOB: ${profile.year_of_birth})`}
              </span>
            </div>
            <div>
              <span className="block text-[10px] uppercase text-slate-500">Height / Weight / BMI:</span>
              <span className="font-mono text-slate-800">
                {profile.height_cm || '—'} cm &middot; {profile.weight_kg || '—'} kg &middot; <strong>{profile.bmi ? `${profile.bmi} kg/m²` : '—'}</strong>
              </span>
            </div>
          </div>

          {/* Box 3: Ayurveda Prakriti Baseline */}
          <div className="border border-slate-200 bg-slate-50 p-3.5 space-y-2">
            <div className="font-bold uppercase tracking-wider text-slate-700 border-b border-slate-200 pb-1 text-[11px]">
              Ayurvedic Constitutional Baseline
            </div>
            <div>
              <span className="block text-[10px] uppercase text-slate-500">Assessed Prakriti:</span>
              <span className="font-bold font-mono uppercase text-slate-900">
                {profile.prakriti ? profile.prakriti.replace('_', '-') : 'Unassessed'}
              </span>
            </div>
            <div>
              <span className="block text-[10px] uppercase text-slate-500">Dosha Classification:</span>
              <span className="text-slate-700">
                {profile.prakriti === 'tridosha'
                  ? 'Samadosha (Equally Balanced)'
                  : profile.prakriti
                  ? `${profile.prakriti.toUpperCase()} Dual-predominance`
                  : 'Pending Clinical Questionnaire'}
              </span>
            </div>
            <div>
              <span className="block text-[10px] uppercase text-slate-500">Social / Ethnicity:</span>
              <span className="text-slate-800">South Asian / Indian</span>
            </div>
          </div>

          {/* Box 4: Consent & DPDP Status */}
          <div className="border border-slate-200 bg-slate-50 p-3.5 space-y-2">
            <div className="font-bold uppercase tracking-wider text-slate-700 border-b border-slate-200 pb-1 text-[11px]">
              Informed Consent & DPDP
            </div>
            <div>
              <span className="block text-[10px] uppercase text-slate-500">Consent Status:</span>
              <span className="font-semibold text-emerald-800">
                {consent.status ? `✓ ${consent.status.toUpperCase()}` : 'Signed (Form CRF-01)'}
              </span>
            </div>
            <div>
              <span className="block text-[10px] uppercase text-slate-500">Signed Timestamp:</span>
              <span className="font-mono text-slate-800">
                {consent.signed_at ? new Date(consent.signed_at).toLocaleString() : 'Documented at Screening'}
              </span>
            </div>
            <div>
              <span className="block text-[10px] uppercase text-slate-500">DPDP Data Masking:</span>
              <span className="font-mono text-[11px] text-slate-700">
                {profile.is_dpdp_masked ? '🔒 PII Masked (Audit Code Active)' : 'Authorized Site Coordinator Access'}
              </span>
            </div>
          </div>
        </div>

        {/* Adverse Events & IEC Ethics Committee Rulings */}
        {dossier.adverse_events && dossier.adverse_events.length > 0 && (
          <div className="border border-slate-200 bg-slate-50 p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-200 pb-2">
              <span className="font-bold uppercase tracking-wider text-slate-800 text-xs flex items-center gap-2">
                <span>🚨</span>
                <span>Reported Adverse Events &amp; Ethics Committee (IEC) Adjudications</span>
              </span>
              <span className="text-[11px] font-mono text-slate-500">
                {dossier.adverse_events.length} Event(s) on file
              </span>
            </div>

            <div className="space-y-2.5">
              {dossier.adverse_events.map((ae) => {
                const isAccepted = ae.ec_decision === 'accepted'
                const isRejected = ae.ec_decision === 'rejected'
                const isActionReq = ae.ec_decision === 'action_required'

                return (
                  <div key={ae.id} className="border border-slate-200 bg-white p-3 text-xs space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-1.5">
                      <div className="flex items-center gap-2 font-mono">
                        <span className="font-bold text-slate-900">{ae.ae_number}</span>
                        <span className="text-slate-400">&bull;</span>
                        <span className="font-sans font-semibold text-slate-800">{ae.term_verbatim}</span>
                        {ae.is_serious && (
                          <span className="bg-rose-100 border border-rose-300 text-rose-800 text-[10px] font-bold px-1.5 py-0.5 uppercase">
                            Serious (SAE)
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] font-mono text-slate-500">
                        Onset: {ae.onset_date} &bull; Severity: <span className="uppercase font-semibold">{ae.severity}</span>
                      </div>
                    </div>

                    {/* IEC Decision Banner */}
                    <div className={`p-2 border flex flex-col sm:flex-row sm:items-center justify-between gap-2 ${
                      isAccepted
                        ? 'border-emerald-300 bg-emerald-50/80 text-emerald-900'
                        : isRejected
                        ? 'border-rose-300 bg-rose-50 text-rose-900'
                        : isActionReq
                        ? 'border-amber-300 bg-amber-50 text-amber-900'
                        : 'border-slate-300 bg-slate-100 text-slate-800'
                    }`}>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-xs">
                          {isAccepted ? '✅ IEC RULING: CLEARED / ACCEPTED' : isRejected ? '❌ IEC RULING: REJECTED / PROTOCOL HALTED' : isActionReq ? '⚠️ IEC QUERY: ACTION REQUIRED' : '⏳ IEC RULING: PENDING COMMITTEE REVIEW'}
                        </span>
                        {ae.ec_decision_date && (
                          <span className="text-[10px] font-mono text-slate-600">
                            (Ruled: {ae.ec_decision_date})
                          </span>
                        )}
                      </div>
                      {ae.ec_decision_notes && (
                        <div className="text-[11px] font-mono italic">
                          Directive: &ldquo;{ae.ec_decision_notes}&rdquo;
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* PART 2: ADD-ENTRY VIEW (Running Clinical Progress Log for Study Coordinator) */}
      {/* ========================================================================= */}
      <div className="border border-slate-300 bg-white p-5 shadow-sm space-y-6">
        <div className="flex items-center justify-between border-b border-slate-200 pb-2.5">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900 flex items-center gap-2">
              Part 2: Running Clinical Progress & Nursing Log
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Append real-time medication administrations, symptoms reported, vital signs, and safety events throughout the study.
            </p>
          </div>
          <span className="border border-slate-800 bg-slate-900 px-3 py-1 font-mono text-[10px] font-bold uppercase text-white">
            Total Logged: {clinicalLogs.length} Entries
          </span>
        </div>

        {/* Existing Chronological Clinical Log (Append-Only Display) */}
        <div className="space-y-3">
          <div className="font-bold uppercase tracking-wider text-slate-800 text-xs border-b border-slate-200 pb-1">
            Clinical Log History (Immutable Audit Record)
          </div>

          {clinicalLogs.length === 0 ? (
            <div className="border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-xs text-slate-500">
              No clinical progress entries logged yet for this participant. Use the entry form below to append observations.
            </div>
          ) : (
            <div className="space-y-3">
              {clinicalLogs.map((entry) => {
                const typeLabels = {
                  medication_administered: { label: 'Medication Administered', badge: 'bg-blue-100 text-blue-900 border-blue-300' },
                  symptom_reported: { label: 'Symptom Reported', badge: 'bg-purple-100 text-purple-900 border-purple-300' },
                  vital_sign: { label: 'Vital Sign Recorded', badge: 'bg-slate-100 text-slate-900 border-slate-300' },
                  adverse_event: { label: 'Adverse Event / Safety Observation', badge: 'bg-red-100 text-red-900 border-red-300 font-bold' },
                  general_note: { label: 'General Clinical Note', badge: 'bg-slate-50 text-slate-800 border-slate-200' },
                }
                const info = typeLabels[entry.entry_type] || { label: entry.entry_type, badge: 'bg-slate-50 text-slate-800 border-slate-200' }

                return (
                  <div
                    key={entry.id}
                    className={`border p-4 text-xs transition ${
                      entry.entry_type === 'adverse_event'
                        ? 'border-red-300 bg-red-50/40'
                        : 'border-slate-200 bg-slate-50/70 hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/80 pb-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-slate-500 text-[11px]">
                          Entry #{entry.id}
                        </span>
                        <span className={`border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${info.badge}`}>
                          {info.label}
                        </span>
                        {entry.linked_ae_id && (
                          <span className="border border-red-400 bg-red-600 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
                            🚨 Escalated to Pharmacovigilance
                          </span>
                        )}
                        {entry.correction_of_entry_id && (
                          <span className="border border-amber-300 bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase text-amber-900">
                            Correction of Entry #{entry.correction_of_entry_id}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-3 font-mono text-[11px] text-slate-500">
                        <span>Attributed: <strong>{entry.entered_by_name}</strong></span>
                        <span>&middot;</span>
                        <span>{new Date(entry.timestamp).toLocaleString()} UTC</span>
                      </div>
                    </div>

                    {/* Substance / Medication specifics */}
                    {entry.substance_name && (
                      <div className="mt-2 grid grid-cols-1 sm:grid-cols-3 gap-2 border border-slate-200 bg-white p-2.5 text-[11px]">
                        <div>
                          <span className="text-slate-500 uppercase font-bold text-[10px]">Substance:</span>{' '}
                          <span className="font-semibold text-slate-900">{entry.substance_name}</span>
                        </div>
                        <div>
                          <span className="text-slate-500 uppercase font-bold text-[10px]">Dose:</span>{' '}
                          <span className="font-semibold text-slate-900">{entry.dose || '—'}</span>
                        </div>
                        <div>
                          <span className="text-slate-500 uppercase font-bold text-[10px]">Route:</span>{' '}
                          <span className="font-semibold text-slate-900">{entry.route || '—'}</span>
                        </div>
                      </div>
                    )}

                    {/* Narrative Description */}
                    <div className="mt-2.5 text-slate-800 leading-relaxed font-sans whitespace-pre-wrap">
                      {entry.observation_description}
                    </div>

                    {/* Correction Rationale */}
                    {entry.correction_reason && (
                      <div className="mt-2 border-l-2 border-amber-500 bg-amber-50 p-2 text-[11px] text-amber-900">
                        <strong>Correction Justification:</strong> {entry.correction_reason}
                      </div>
                    )}

                    {/* Footer Actions */}
                    <div className="mt-3 flex items-center justify-between pt-2 border-t border-slate-200 text-[11px]">
                      <div className="text-slate-400 font-mono text-[10px]">
                        Cryptographically Sealed &middot; ALCOA+ Immutable Record
                      </div>
                      <button
                        type="button"
                        onClick={() => handleStartCorrection(entry)}
                        className="font-semibold text-slate-600 underline hover:text-slate-900"
                      >
                        Append Addendum / Correction referencing #{entry.id}
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* New Entry Form */}
        <div className="border border-slate-300 bg-slate-50 p-5">
          <div className="border-b border-slate-200 pb-2 mb-4 flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
              {isCorrection ? `Append Correction Entry (Referencing #${correctionOfEntryId})` : 'Append New Clinical Progress Entry'}
            </h3>
            {isCorrection && (
              <button
                type="button"
                onClick={() => {
                  setIsCorrection(false)
                  setCorrectionOfEntryId('')
                  setCorrectionReason('')
                  setObservationDescription('')
                }}
                className="text-xs font-bold text-red-700 underline"
              >
                Cancel Correction Mode
              </button>
            )}
          </div>

          {submitSuccess && (
            <div className="mb-4 border border-emerald-400 bg-emerald-50 p-3 text-xs font-semibold text-emerald-900">
              ✓ {submitSuccess}
            </div>
          )}

          {submitError && (
            <div className="mb-4 border border-red-400 bg-red-50 p-3 text-xs font-semibold text-red-900">
              <strong>Error:</strong> {submitError}
            </div>
          )}

          <form onSubmit={handleAddLogSubmit} className="space-y-4 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <label className="block font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Controlled Entry Type *
                </label>
                <select
                  value={entryType}
                  onChange={(e) => setEntryType(e.target.value)}
                  className="w-full border border-slate-300 bg-white p-2 text-xs font-medium text-slate-900 focus:border-slate-800 focus:outline-none"
                  required
                >
                  <option value="medication_administered">Medication Administered</option>
                  <option value="symptom_reported">Symptom Reported</option>
                  <option value="vital_sign">Vital Sign Recorded</option>
                  <option value="adverse_event">Adverse Event (Triggers Pharmacovigilance)</option>
                  <option value="general_note">General Clinical Note</option>
                </select>
              </div>

              <div>
                <label className="block font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Linked Protocol Visit (Optional)
                </label>
                <select
                  value={linkedVisitId}
                  onChange={(e) => setLinkedVisitId(e.target.value)}
                  className="w-full border border-slate-300 bg-white p-2 text-xs font-medium text-slate-900 focus:border-slate-800 focus:outline-none"
                >
                  <option value="">-- No specific visit milestone linked --</option>
                  {visits.map((v) => (
                    <option key={v.id} value={v.id}>
                      Visit {v.visit_number}: {v.visit_name} ({v.status})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Entered By (System Session Attributed)
                </label>
                <input
                  type="text"
                  readOnly
                  disabled
                  value={`${user?.full_name} (${user?.role_label})`}
                  className="w-full border border-slate-200 bg-slate-100 p-2 font-semibold text-slate-700 cursor-not-allowed select-none"
                />
              </div>
            </div>

            {/* Conditional Substance details if Medication Administered */}
            {entryType === 'medication_administered' && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 border border-blue-200 bg-blue-50/40 p-3">
                <div>
                  <label className="block font-bold uppercase tracking-wider text-blue-950 mb-1">
                    Medicine / Substance Name *
                  </label>
                  <input
                    type="text"
                    value={substanceName}
                    onChange={(e) => setSubstanceName(e.target.value)}
                    placeholder="e.g. Ashwagandha Root Churna"
                    className="w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block font-bold uppercase tracking-wider text-blue-950 mb-1">
                    Dose / Strength *
                  </label>
                  <input
                    type="text"
                    value={dose}
                    onChange={(e) => setDose(e.target.value)}
                    placeholder="e.g. 500 mg BD"
                    className="w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block font-bold uppercase tracking-wider text-blue-950 mb-1">
                    Route of Administration *
                  </label>
                  <input
                    type="text"
                    value={route}
                    onChange={(e) => setRoute(e.target.value)}
                    placeholder="e.g. Oral with lukewarm milk / water"
                    className="w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
                    required
                  />
                </div>
              </div>
            )}

            {/* Conditional Adverse Event fields */}
            {entryType === 'adverse_event' && (
              <div className="border border-red-300 bg-red-50/70 p-3.5 space-y-3">
                <div className="font-bold text-red-950 uppercase tracking-wider text-[11px] flex items-center gap-2">
                  <span>🚨 Pharmacovigilance Module Trigger Active</span>
                  <span className="font-normal font-mono text-[10px] text-red-800">
                    (Automatically logs regulatory event in safety ledger)
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block font-bold uppercase tracking-wider text-red-900 mb-1">
                      Event Severity
                    </label>
                    <select
                      value={aeSeverity}
                      onChange={(e) => setAeSeverity(e.target.value)}
                      className="w-full border border-red-300 bg-white p-2 text-xs font-semibold text-red-950 focus:outline-none"
                    >
                      <option value="mild">Mild - Easily tolerated, minimal interference</option>
                      <option value="moderate">Moderate - Discomfort interferes with normal activity</option>
                      <option value="severe">Severe - Incapacitating, unable to perform work/ADLs</option>
                    </select>
                  </div>

                  <div className="flex items-center pt-5">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={isSerious}
                        onChange={(e) => setIsSerious(e.target.checked)}
                        className="h-4 w-4 border-red-300 text-red-600 focus:ring-0"
                      />
                      <span className="font-bold text-red-900 text-xs">
                        Serious Adverse Event (SAE) — Initiates Mandatory 24h CDSCO Clock
                      </span>
                    </label>
                  </div>
                </div>
              </div>
            )}

            {/* If in correction mode, demand correction reason */}
            {isCorrection && (
              <div className="border border-amber-300 bg-amber-50 p-3">
                <label className="block font-bold uppercase tracking-wider text-amber-900 mb-1">
                  ALCOA+ Correction Justification *
                </label>
                <input
                  type="text"
                  value={correctionReason}
                  onChange={(e) => setCorrectionReason(e.target.value)}
                  placeholder="e.g. Transcription error in dosage; corrected following source sheet verification."
                  className="w-full border border-amber-300 bg-white p-2 text-xs text-slate-900 focus:outline-none"
                  required
                />
              </div>
            )}

            <div>
              <label className="block font-bold uppercase tracking-wider text-slate-700 mb-1">
                Clinical Observation / Progress Narrative *
              </label>
              <textarea
                rows="3"
                value={observationDescription}
                onChange={(e) => setObservationDescription(e.target.value)}
                placeholder="Enter clinical observations, participant self-reported symptoms, vital signs readings, or nursing notes..."
                className="w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none font-sans"
                required
              />
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-200">
              <div className="text-[11px] text-slate-500 font-mono">
                System timestamp: <strong>{new Date().toUTCString()}</strong> &middot; Non-editable
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="border border-slate-900 bg-slate-900 px-6 py-2.5 text-xs font-bold uppercase tracking-wider text-white hover:bg-slate-800 disabled:opacity-50 transition shadow-sm"
              >
                {submitting ? 'Committing Entry...' : isCorrection ? 'Commit Correction Note' : 'Commit Entry to Clinical Log'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
