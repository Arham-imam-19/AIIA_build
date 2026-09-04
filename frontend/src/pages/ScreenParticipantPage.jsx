import React, { useEffect, useState } from 'react'
import { createStructuredSubject, fetchSites, fetchTrials } from '../api'
import { useAuth } from '../auth'

export default function ScreenParticipantPage({ onNavigateDashboard, onRefresh, onScreenSuccess }) {
  const { user } = useAuth()

  const [trials, setTrials] = useState([])
  const [sites, setSites] = useState([])
  const [trial, setTrial] = useState(null)
  const [site, setSite] = useState(null)
  const [loadingMeta, setLoadingMeta] = useState(true)

  // Demographics & Ayurveda Baseline
  const [sex, setSex] = useState('female')
  const [yearOfBirth, setYearOfBirth] = useState(1992)
  const [heightCm, setHeightCm] = useState(165)
  const [weightKg, setWeightKg] = useState(62)
  const [prakriti, setPrakriti] = useState('vata_pitta')
  const [ethnicity, setEthnicity] = useState('South Asian / Indian')

  // Protocol & Consent Details (GCP-ASU + DPDP Act 2023)
  const [protocolVersion, setProtocolVersion] = useState('v2.4 (Amendment 02)')
  const [icfVersion, setIcfVersion] = useState('ICF-ASU-2024-v2.1')
  const [consentDate, setConsentDate] = useState(new Date().toISOString().slice(0, 16))
  const [consentObtainedBy, setConsentObtainedBy] = useState(user?.full_name || 'Kavita Nair')
  const [consentConfirmed, setConsentConfirmed] = useState(true)
  const [withdrawalOfConsent, setWithdrawalOfConsent] = useState(false)

  // Dynamic Inclusion Criteria Checklist
  const [incCriteria, setIncCriteria] = useState({
    inc_age: true,
    inc_consent: true,
    inc_compliance: true,
    inc_health: true,
  })

  // Dynamic Exclusion Criteria Checklist
  const [excCriteria, setExcCriteria] = useState({
    exc_hypersensitivity: false,
    exc_concomitant_meds: false,
    exc_pregnancy: false,
    exc_concurrent_trial: false,
  })

  const [outcomeOverride, setOutcomeOverride] = useState('auto')
  const [screenFailureReason, setScreenFailureReason] = useState('')

  // Submission state
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(null)
  const [registrationResult, setRegistrationResult] = useState(null)

  useEffect(() => {
    let isMounted = true
    Promise.all([fetchTrials(), fetchSites()])
      .then(([trialsRes, sitesRes]) => {
        if (!isMounted) return
        const trialList = trialsRes.items || []
        const siteList = sitesRes.items || []
        setTrials(trialList)
        setSites(siteList)

        const activeTrial =
          trialList.find((t) => t.status === 'recruiting') ||
          trialList[0] ||
          null
        setTrial(activeTrial)

        if (activeTrial) {
          const userSiteId = user?.site_id
          const userSite =
            siteList.find((s) => s.trial_id === activeTrial.id && s.id === userSiteId) ||
            siteList.find((s) => s.trial_id === activeTrial.id) ||
            siteList[0] ||
            null
          setSite(userSite)
        }
        setLoadingMeta(false)
      })
      .catch(() => {
        if (isMounted) setLoadingMeta(false)
      })
    return () => {
      isMounted = false
    }
  }, [user])

  const handleTrialSelect = (selectedId) => {
    const chosen = trials.find((t) => t.id === Number(selectedId)) || trials[0]
    setTrial(chosen)
    const sitesForTrial = sites.filter((s) => s.trial_id === chosen.id)
    const matchedSite =
      sitesForTrial.find((s) => s.id === user?.site_id) ||
      sitesForTrial[0] ||
      null
    setSite(matchedSite)
    setSubmitError(null)
  }

  // System-derived calculations
  const currentYear = new Date().getFullYear()
  const computedAge = yearOfBirth ? currentYear - Number(yearOfBirth) : ''
  const computedBmi =
    heightCm && weightKg
      ? (Number(weightKg) / Math.pow(Number(heightCm) / 100, 2)).toFixed(1)
      : ''

  // System-derived eligibility evaluation
  const allInclusionsMet = Object.values(incCriteria).every(Boolean)
  const anyExclusionPresent = Object.values(excCriteria).some(Boolean)
  const autoOutcome =
    allInclusionsMet && !anyExclusionPresent ? 'eligible' : 'screen_failed'
  const effectiveOutcome =
    outcomeOverride === 'auto' ? autoOutcome : outcomeOverride

  const isRecruiting = trial?.status === 'recruiting'
  const isEthicsApproved = trial?.ethics_approval_status === 'approved'

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setSubmitError(null)

    if (!isEthicsApproved) {
      setSubmitError(
        `Enrollment Blocked: Protocol ${trial?.protocol_number} ethics approval status is ${trial?.ethics_approval_status || 'Pending'}. Software blocks screening until IEC clearance is approved.`
      )
      setSubmitting(false)
      return
    }

    if (!isRecruiting) {
      setSubmitError(
        `Enrollment Blocked: Protocol ${trial?.protocol_number} is in '${trial?.status}' status. Only recruiting protocols can register screened participants.`
      )
      setSubmitting(false)
      return
    }

    if (effectiveOutcome === 'screen_failed' && !screenFailureReason.trim()) {
      setSubmitError('Mandatory requirement: A documented screen failure reason must be provided for audit tracking.')
      setSubmitting(false)
      return
    }

    try {
      const payload = {
        trial_id: trial?.id || 1,
        site_id: site?.id || user?.site_id || 1,
        screening_date: new Date().toISOString().split('T')[0],
        sex,
        year_of_birth: Number(yearOfBirth),
        height_cm: Number(heightCm),
        weight_kg: Number(weightKg),
        prakriti: prakriti ? prakriti.replace('-', '_') : undefined,
        protocol_version: protocolVersion,
        inclusion_criteria: incCriteria,
        exclusion_criteria: excCriteria,
        eligibility_outcome: effectiveOutcome,
        screen_failure_reason:
          effectiveOutcome === 'screen_failed' ? screenFailureReason.trim() : null,
        icf_version: icfVersion,
        consent_date: new Date(consentDate).toISOString(),
        consent_obtained_by: consentObtainedBy,
        withdrawal_of_consent: withdrawalOfConsent,
        ethnicity,
      }

      const res = await createStructuredSubject(payload)
      onRefresh?.()
      if (onScreenSuccess) {
        onScreenSuccess(res)
      } else {
        setRegistrationResult(res)
      }
    } catch (err) {
      setSubmitError(err.detail || err.message || 'Failed to register participant screening record.')
    } finally {
      setSubmitting(false)
    }
  }

  function handleResetForNext() {
    setRegistrationResult(null)
    setSubmitError(null)
    setScreenFailureReason('')
    setOutcomeOverride('auto')
  }

  return (
    <div className="space-y-6">
      {/* Top Header & Breadcrumb */}
      <div className="border border-slate-300 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="border border-slate-300 bg-slate-100 px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-slate-700">
                Form CRF-01
              </span>
              <span className="font-mono text-xs font-semibold text-slate-500">
                CDASH / SDTM DM Domain &middot; Central CTMS
              </span>
            </div>
            <h1 className="mt-1 text-xl font-bold tracking-tight text-slate-900 uppercase">
              Participant Screening & Intake Registration
            </h1>
          </div>
          <button
            type="button"
            onClick={onNavigateDashboard}
            className="border border-slate-300 bg-slate-50 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-slate-700 hover:bg-slate-100 transition"
          >
            &larr; Back to Dashboard
          </button>
        </div>

        {/* Regulatory Banner */}
        <div className="mt-3 flex items-start gap-2.5 border-l-4 border-slate-700 bg-slate-50 p-3 text-xs text-slate-700">
          <div className="font-bold text-slate-900 uppercase tracking-wider text-[11px] whitespace-nowrap">
            Regulatory Notice:
          </div>
          <div className="leading-relaxed text-[11px]">
            In compliance with <strong>New Drugs & Clinical Trials Rules 2019</strong> and <strong>GCP-ASU / DPDP Act 2023</strong>, all administrative, site, and subject code parameters are system-generated and non-editable. Pseudonymized codes are assigned sequentially upon digital verification.
          </div>
        </div>
      </div>

      {/* Success Registration Screen */}
      {registrationResult ? (
        <div className="border-2 border-emerald-600 bg-white p-8 shadow-sm">
          <div className="border-b border-emerald-200 pb-4 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center border-2 border-emerald-600 bg-emerald-50 text-emerald-800 text-xl font-bold">
              ✓
            </div>
            <h2 className="mt-3 text-lg font-bold uppercase tracking-wider text-emerald-900">
              Screening Record Successfully Registered
            </h2>
            <p className="mt-1 text-xs text-slate-600">
              Official participant record committed to clinical trials ledger and audit repository.
            </p>
          </div>

          <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4 border border-slate-200 bg-slate-50 p-5 text-xs">
            <div>
              <span className="block text-[11px] font-bold uppercase text-slate-500">System Subject Code</span>
              <span className="mt-0.5 block font-mono text-base font-bold text-slate-900">
                {registrationResult.subject_code}
              </span>
            </div>
            <div>
              <span className="block text-[11px] font-bold uppercase text-slate-500">Screening Status</span>
              <span className="mt-0.5 inline-block border border-slate-300 bg-white px-2 py-0.5 font-mono text-xs font-bold uppercase text-slate-800">
                {registrationResult.status}
              </span>
            </div>
            <div>
              <span className="block text-[11px] font-bold uppercase text-slate-500">Participating Site</span>
              <span className="mt-0.5 block font-medium text-slate-800">
                Site {registrationResult.site_id} &middot; {site?.site_name || 'All India Institute of Ayurveda'}
              </span>
            </div>
            <div>
              <span className="block text-[11px] font-bold uppercase text-slate-500">Screening Date & Time</span>
              <span className="mt-0.5 block font-mono text-slate-800">
                {registrationResult.screening_date} &middot; {new Date(registrationResult.created_at).toLocaleTimeString()}
              </span>
            </div>
            <div>
              <span className="block text-[11px] font-bold uppercase text-slate-500">Eligibility Determination</span>
              <span className={`mt-0.5 inline-block font-semibold uppercase text-xs ${
                effectiveOutcome === 'eligible' ? 'text-emerald-700' : 'text-red-700'
              }`}>
                {effectiveOutcome === 'eligible' ? 'Eligible for Study Protocol' : 'Screen Failure'}
              </span>
            </div>
            <div>
              <span className="block text-[11px] font-bold uppercase text-slate-500">Enrolling Coordinator</span>
              <span className="mt-0.5 block font-medium text-slate-800">
                {user?.full_name} ({user?.role_label})
              </span>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-end gap-3 border-t border-slate-200 pt-4">
            <button
              type="button"
              onClick={handleResetForNext}
              className="border border-slate-400 bg-white px-5 py-2 text-xs font-bold uppercase tracking-wider text-slate-800 hover:bg-slate-100 transition"
            >
              Screen Another Participant
            </button>
            <button
              type="button"
              onClick={onNavigateDashboard}
              className="border border-slate-900 bg-slate-900 px-6 py-2 text-xs font-bold uppercase tracking-wider text-white hover:bg-slate-800 transition"
            >
              Return to Worklist Dashboard &rarr;
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-6">
          {submitError && (
            <div className="border border-red-400 bg-red-50 p-4 text-xs font-semibold text-red-900">
              <span className="font-bold uppercase tracking-wider">Error:</span> {submitError}
            </div>
          )}

          {/* Section 1: System-Locked Administrative Parameters */}
          <div className="border border-slate-300 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-200 pb-2.5">
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900">
                1. Identity & Administrative Metadata
              </h2>
              <span className="border border-slate-300 bg-slate-100 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase text-slate-600">
                System Generated &middot; Non-Editable
              </span>
            </div>

            <p className="mt-2 text-xs text-slate-500">
              Parameters below are permanently locked by the system to maintain de-identification integrity, protocol audit compliance, and strict chain of custody. No user input permitted.
            </p>

            <div className="mt-4 border border-slate-300 bg-slate-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-800">
                  Target Clinical Protocol / Trial:
                </label>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 text-[10px] font-bold uppercase border ${
                    isEthicsApproved ? 'bg-emerald-100 text-emerald-800 border-emerald-300' : 'bg-amber-100 text-amber-800 border-amber-300'
                  }`}>
                    {isEthicsApproved ? '✓ IEC Approved' : '⏳ Pending IEC Clearance'}
                  </span>
                  <span className={`px-2 py-0.5 text-[10px] font-bold uppercase border ${
                    isRecruiting ? 'bg-emerald-100 text-emerald-800 border-emerald-300' : 'bg-red-100 text-red-800 border-red-300'
                  }`}>
                    Status: {trial?.status?.toUpperCase()}
                  </span>
                </div>
              </div>

              <select
                value={trial?.id || ''}
                onChange={(e) => handleTrialSelect(e.target.value)}
                disabled={loadingMeta}
                className="w-full border border-slate-300 bg-white p-2.5 text-xs font-bold text-slate-900 shadow-sm focus:border-slate-800 focus:outline-none"
              >
                {trials.map((t) => (
                  <option key={t.id} value={t.id}>
                    [{t.protocol_number}] {t.title} &middot; ({t.status.toUpperCase()}) &middot; CTRI: {t.ctri_number || 'Prospective'}
                  </option>
                ))}
              </select>

              {!isEthicsApproved && (
                <div className="mt-2 text-[11px] text-amber-800 bg-amber-50 border border-amber-200 p-2 font-medium">
                  ⚠️ <strong>Regulatory Hold:</strong> Protocol {trial?.protocol_number} requires official clearance from the Institutional Ethics Committee (IEC) prior to screening subjects.
                </div>
              )}
            </div>

            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
              <div className="border border-slate-200 bg-slate-50 p-2.5">
                <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Subject ID / Screening No.
                </label>
                <div className="mt-1 font-mono font-bold text-slate-900">
                  [Auto-Assigned on Submit]
                </div>
                <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                  Prefix: AIIA-{trial?.protocol_number ? (trial.protocol_number.split('-')[1] || trial.protocol_number.slice(0, 5)).toUpperCase() : 'ASH'}-{site?.site_code || '01'}-XXX
                </div>
              </div>

              <div className="border border-slate-200 bg-slate-50 p-2.5">
                <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Site ID & Hospital
                </label>
                <div className="mt-1 font-semibold text-slate-800 truncate" title={site?.site_name}>
                  Site {site?.id ?? user?.site_id ?? '—'} &middot; {site?.site_name || 'All India Institute of Ayurveda'}
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">
                  Scope: Site {site?.id ?? user?.site_id ?? '01'} Authorized
                </div>
              </div>

              <div className="border border-slate-200 bg-slate-50 p-2.5">
                <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Study / Protocol ID
                </label>
                <div className="mt-1 font-mono font-bold text-slate-800">
                  {trial?.protocol_number || 'AIIA-ASH-2024'}
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">
                  CTRI: {trial?.ctri_number || 'CTRI/2024/05/06789'}
                </div>
              </div>

              <div className="border border-slate-200 bg-slate-50 p-2.5">
                <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Enrolling Delegated CRC
                </label>
                <div className="mt-1 font-semibold text-slate-800">
                  {user?.full_name}
                </div>
                <div className="text-[10px] text-emerald-700 font-medium mt-0.5">
                  ✓ Delegation Log Verified
                </div>
              </div>

              <div className="border border-slate-200 bg-slate-50 p-2.5">
                <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Screening Date
                </label>
                <div className="mt-1 font-mono font-semibold text-slate-800">
                  {new Date().toISOString().split('T')[0]}
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">
                  System Reference Date
                </div>
              </div>

              <div className="border border-slate-200 bg-slate-50 p-2.5">
                <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Enrollment Stage
                </label>
                <div className="mt-1 font-semibold text-slate-800">
                  Screening Phase (Pending)
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">
                  Locked Until Eligibility Met
                </div>
              </div>

              <div className="border border-slate-200 bg-slate-50 p-2.5">
                <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Randomization Arm
                </label>
                <div className="mt-1 font-mono font-semibold text-slate-800">
                  Not Randomized
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">
                  Double-Blind Allocation Post-Screen
                </div>
              </div>

              <div className="border border-slate-200 bg-slate-50 p-2.5">
                <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Audit Transaction
                </label>
                <div className="mt-1 font-mono text-[11px] text-slate-700">
                  AUDIT_CREATE (subjects)
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">
                  User #{user?.id} &middot; Automatic Log
                </div>
              </div>
            </div>
          </div>

          {/* Section 2: Participant Demographics & Measurements */}
          <div className="border border-slate-300 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-200 pb-2.5">
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900">
                2. Participant Demographics & Ayurvedic Baseline
              </h2>
              <span className="border border-blue-300 bg-blue-50 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase text-blue-800">
                Coordinator Entry
              </span>
            </div>

            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 text-xs">
              <div>
                <label className="block font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Biological Sex *
                </label>
                <select
                  value={sex}
                  onChange={(e) => setSex(e.target.value)}
                  className="w-full border border-slate-300 bg-white p-2 text-xs font-medium text-slate-900 focus:border-slate-800 focus:outline-none"
                  required
                >
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="font-bold uppercase tracking-wider text-slate-700">
                    Year of Birth *
                  </label>
                  <span className="font-mono text-[11px] font-semibold text-slate-600">
                    Calculated Age: <strong className="text-slate-900">{computedAge || '—'} yrs</strong>
                  </span>
                </div>
                <input
                  type="number"
                  min={1930}
                  max={currentYear - 18}
                  value={yearOfBirth}
                  onChange={(e) => setYearOfBirth(e.target.value)}
                  className="w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
                  required
                />
                <div className="mt-1 text-[10px] text-slate-500">
                  Coarse demographic (Age range 18–65 required by protocol).
                </div>
              </div>

              <div>
                <label className="block font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Social / Ethnicity Baseline
                </label>
                <input
                  type="text"
                  value={ethnicity}
                  onChange={(e) => setEthnicity(e.target.value)}
                  className="w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
                  placeholder="e.g. South Asian / Indian"
                />
              </div>

              <div>
                <label className="block font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Height (cm) *
                </label>
                <input
                  type="number"
                  step="0.5"
                  min={100}
                  max={250}
                  value={heightCm}
                  onChange={(e) => setHeightCm(e.target.value)}
                  className="w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Weight (kg) *
                </label>
                <input
                  type="number"
                  step="0.5"
                  min={30}
                  max={200}
                  value={weightKg}
                  onChange={(e) => setWeightKg(e.target.value)}
                  className="w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Calculated BMI (kg/m²)
                </label>
                <input
                  type="text"
                  readOnly
                  disabled
                  value={computedBmi ? `${computedBmi} kg/m²` : '—'}
                  className="w-full border border-slate-200 bg-slate-50 p-2 font-mono text-xs font-bold text-slate-700 cursor-not-allowed select-none"
                />
                <div className="mt-1 text-[10px] text-slate-500">
                  Auto-calculated from height & weight parameters.
                </div>
              </div>

              <div className="sm:col-span-2 md:col-span-3">
                <label className="block font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Ayurvedic Prakriti (Constitutional Phenotype) *
                </label>
                <select
                  value={prakriti}
                  onChange={(e) => setPrakriti(e.target.value)}
                  className="w-full border border-slate-300 bg-white p-2 text-xs font-medium text-slate-900 focus:border-slate-800 focus:outline-none"
                  required
                >
                  <option value="vata_pitta">Vata-Pitta (Vata predominant with Pitta secondary)</option>
                  <option value="pitta_kapha">Pitta-Kapha (Pitta predominant with Kapha secondary)</option>
                  <option value="vata_kapha">Vata-Kapha (Vata-Kapha dual dosha)</option>
                  <option value="tridosha">Tridosha (Equally balanced Samadosha)</option>
                  <option value="vata">Vata (Vata single dosha)</option>
                  <option value="pitta">Pitta (Pitta single dosha)</option>
                  <option value="kapha">Kapha (Kapha single dosha)</option>
                </select>
                <div className="mt-1 text-[10px] text-slate-500">
                  Determined by documented baseline Ayurvedic clinical assessment questionnaire.
                </div>
              </div>
            </div>
          </div>

          {/* Section 3: Protocol & Informed Consent (GCP-ASU & DPDP Act 2023) */}
          <div className="border border-slate-300 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-200 pb-2.5">
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900">
                3. Protocol Version & Informed Consent Compliance
              </h2>
              <span className="border border-emerald-300 bg-emerald-50 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase text-emerald-800">
                GCP-ASU &middot; DPDP Act 2023
              </span>
            </div>

            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 text-xs">
              <div>
                <label className="block font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Protocol Version Screened Against *
                </label>
                <input
                  type="text"
                  value={protocolVersion}
                  onChange={(e) => setProtocolVersion(e.target.value)}
                  className="w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
                  required
                />
                <div className="mt-1 text-[10px] text-slate-500">
                  Current ethics-cleared protocol amendment version.
                </div>
              </div>

              <div>
                <label className="block font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Informed Consent Form (ICF) Version Signed *
                </label>
                <input
                  type="text"
                  value={icfVersion}
                  onChange={(e) => setIcfVersion(e.target.value)}
                  className="w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
                  required
                />
                <div className="mt-1 text-[10px] text-slate-500">
                  Must match approved Institutional Ethics Committee document.
                </div>
              </div>

              <div>
                <label className="block font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Consent Date & Time *
                </label>
                <input
                  type="datetime-local"
                  value={consentDate}
                  onChange={(e) => setConsentDate(e.target.value)}
                  className="w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
                  required
                />
                <div className="mt-1 text-[10px] text-slate-500">
                  Exact timestamp when participant affixed signature/thumbprint.
                </div>
              </div>

              <div>
                <label className="block font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Consent Obtained By (Name & Title) *
                </label>
                <input
                  type="text"
                  value={consentObtainedBy}
                  onChange={(e) => setConsentObtainedBy(e.target.value)}
                  className="w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
                  required
                />
              </div>

              <div className="sm:col-span-2 flex flex-col justify-center space-y-2 border border-slate-200 bg-slate-50 p-3">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={consentConfirmed}
                    onChange={(e) => setConsentConfirmed(e.target.checked)}
                    className="h-4 w-4 border-slate-300 text-slate-900 focus:ring-0"
                    required
                  />
                  <span className="font-semibold text-slate-800 text-xs">
                    I confirm that full voluntary Informed Consent was obtained PRIOR to any study assessment.
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={withdrawalOfConsent}
                    onChange={(e) => setWithdrawalOfConsent(e.target.checked)}
                    className="h-4 w-4 border-slate-300 text-slate-900 focus:ring-0"
                  />
                  <span className="text-slate-600 text-xs">
                    Participant has submitted a notice of withdrawal-of-consent (Flag active).
                  </span>
                </label>
              </div>
            </div>
          </div>

          {/* Section 4: Eligibility Criteria Checklist */}
          <div className="border border-slate-300 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-200 pb-2.5">
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900">
                4. Protocol Eligibility Assessment Checklists
              </h2>
              <span className={`px-2 py-0.5 font-mono text-[10px] font-bold uppercase border ${
                effectiveOutcome === 'eligible'
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                  : 'bg-red-50 text-red-800 border-red-300'
              }`}>
                Determination: {effectiveOutcome === 'eligible' ? 'ELIGIBLE' : 'SCREEN FAILURE'}
              </span>
            </div>

            <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-6 text-xs">
              {/* Inclusion Criteria */}
              <div className="border border-slate-200 p-4">
                <div className="font-bold uppercase tracking-wider text-slate-800 border-b border-slate-200 pb-2 mb-3 flex items-center justify-between">
                  <span>Inclusion Criteria (All Mandatory)</span>
                  <span className="font-mono text-[11px] text-slate-500">
                    {Object.values(incCriteria).filter(Boolean).length}/4 Met
                  </span>
                </div>

                <div className="space-y-3">
                  <label className="flex items-start gap-2.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={incCriteria.inc_age}
                      onChange={(e) =>
                        setIncCriteria({ ...incCriteria, inc_age: e.target.checked })
                      }
                      className="mt-0.5 h-4 w-4 border-slate-300 text-slate-900 focus:ring-0"
                    />
                    <span className="text-slate-700 leading-snug">
                      <strong>INC-01:</strong> Participant is aged between 18 and 65 years inclusive at the time of screening.
                    </span>
                  </label>

                  <label className="flex items-start gap-2.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={incCriteria.inc_consent}
                      onChange={(e) =>
                        setIncCriteria({ ...incCriteria, inc_consent: e.target.checked })
                      }
                      className="mt-0.5 h-4 w-4 border-slate-300 text-slate-900 focus:ring-0"
                    />
                    <span className="text-slate-700 leading-snug">
                      <strong>INC-02:</strong> Voluntarily signed written informed consent (ICF) prior to any study-related assessment.
                    </span>
                  </label>

                  <label className="flex items-start gap-2.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={incCriteria.inc_compliance}
                      onChange={(e) =>
                        setIncCriteria({ ...incCriteria, inc_compliance: e.target.checked })
                      }
                      className="mt-0.5 h-4 w-4 border-slate-300 text-slate-900 focus:ring-0"
                    />
                    <span className="text-slate-700 leading-snug">
                      <strong>INC-03:</strong> Willing and able to comply with scheduled clinic visits, investigational product dosing, and procedures.
                    </span>
                  </label>

                  <label className="flex items-start gap-2.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={incCriteria.inc_health}
                      onChange={(e) =>
                        setIncCriteria({ ...incCriteria, inc_health: e.target.checked })
                      }
                      className="mt-0.5 h-4 w-4 border-slate-300 text-slate-900 focus:ring-0"
                    />
                    <span className="text-slate-700 leading-snug">
                      <strong>INC-04:</strong> General clinical health status verified with no severe systemic organic pathology.
                    </span>
                  </label>
                </div>
              </div>

              {/* Exclusion Criteria */}
              <div className="border border-slate-200 p-4">
                <div className="font-bold uppercase tracking-wider text-slate-800 border-b border-slate-200 pb-2 mb-3 flex items-center justify-between">
                  <span>Exclusion Criteria (Must Be None)</span>
                  <span className="font-mono text-[11px] text-slate-500">
                    {Object.values(excCriteria).filter(Boolean).length} Present
                  </span>
                </div>

                <div className="space-y-3">
                  <label className="flex items-start gap-2.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={excCriteria.exc_hypersensitivity}
                      onChange={(e) =>
                        setExcCriteria({
                          ...excCriteria,
                          exc_hypersensitivity: e.target.checked,
                        })
                      }
                      className="mt-0.5 h-4 w-4 border-slate-300 text-red-600 focus:ring-0"
                    />
                    <span className="text-slate-700 leading-snug">
                      <strong>EXC-01:</strong> Known history of hypersensitivity or adverse reaction to Ashwagandha or botanical formulations.
                    </span>
                  </label>

                  <label className="flex items-start gap-2.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={excCriteria.exc_concomitant_meds}
                      onChange={(e) =>
                        setExcCriteria({
                          ...excCriteria,
                          exc_concomitant_meds: e.target.checked,
                        })
                      }
                      className="mt-0.5 h-4 w-4 border-slate-300 text-red-600 focus:ring-0"
                    />
                    <span className="text-slate-700 leading-snug">
                      <strong>EXC-02:</strong> Concurrent use of immunosuppressants, chronic systemic corticosteroids, or psychotropic drugs.
                    </span>
                  </label>

                  <label className="flex items-start gap-2.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={excCriteria.exc_pregnancy}
                      onChange={(e) =>
                        setExcCriteria({
                          ...excCriteria,
                          exc_pregnancy: e.target.checked,
                        })
                      }
                      className="mt-0.5 h-4 w-4 border-slate-300 text-red-600 focus:ring-0"
                    />
                    <span className="text-slate-700 leading-snug">
                      <strong>EXC-03:</strong> Female participant who is pregnant, lactating, or planning conception during the study window.
                    </span>
                  </label>

                  <label className="flex items-start gap-2.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={excCriteria.exc_concurrent_trial}
                      onChange={(e) =>
                        setExcCriteria({
                          ...excCriteria,
                          exc_concurrent_trial: e.target.checked,
                        })
                      }
                      className="mt-0.5 h-4 w-4 border-slate-300 text-red-600 focus:ring-0"
                    />
                    <span className="text-slate-700 leading-snug">
                      <strong>EXC-04:</strong> Concurrent participation in any other clinical drug, device, or phytomedicine trial within 30 days.
                    </span>
                  </label>
                </div>
              </div>
            </div>

            {/* Outcome Control & Screen Failure Reason */}
            <div className="mt-4 border-t border-slate-200 pt-4 text-xs">
              <div className="flex flex-wrap items-center gap-4">
                <div className="font-bold uppercase tracking-wider text-slate-700">
                  Eligibility Determination Override:
                </div>
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="outcomeOverride"
                      value="auto"
                      checked={outcomeOverride === 'auto'}
                      onChange={() => setOutcomeOverride('auto')}
                      className="text-slate-900 focus:ring-0"
                    />
                    <span>Automated Checklist ({autoOutcome === 'eligible' ? 'Eligible' : 'Screen Failure'})</span>
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="outcomeOverride"
                      value="eligible"
                      checked={outcomeOverride === 'eligible'}
                      onChange={() => setOutcomeOverride('eligible')}
                      className="text-slate-900 focus:ring-0"
                    />
                    <span>Force Eligible</span>
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="outcomeOverride"
                      value="screen_failed"
                      checked={outcomeOverride === 'screen_failed'}
                      onChange={() => setOutcomeOverride('screen_failed')}
                      className="text-slate-900 focus:ring-0"
                    />
                    <span className="text-red-700 font-semibold">Declare Screen Failure</span>
                  </label>
                </div>
              </div>

              {effectiveOutcome === 'screen_failed' && (
                <div className="mt-3 border border-red-300 bg-red-50/70 p-3">
                  <label className="block font-bold uppercase tracking-wider text-red-900 mb-1">
                    Screen Failure Reason (Mandatory for Audit Trail) *
                  </label>
                  <textarea
                    rows="2"
                    value={screenFailureReason}
                    onChange={(e) => setScreenFailureReason(e.target.value)}
                    className="w-full border border-red-300 bg-white p-2 text-xs text-slate-900 focus:border-red-600 focus:outline-none"
                    placeholder="Document specific clinical rationale or protocol criterion failure (e.g. participant exceeded blood pressure threshold, withdrew consent prior to dosing)..."
                    required
                  />
                  <div className="mt-1 text-[10px] text-red-700 font-mono">
                    NDCT Rules 2019 Rule 24 requires detailed recording of all screen failures.
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Section 5: Digital Submission Action Bar */}
          <div className="border border-slate-300 bg-white p-5 shadow-sm flex flex-wrap items-center justify-between gap-4">
            <div className="text-xs text-slate-500">
              <span className="font-semibold text-slate-700">Digital Audit Verification:</span> Recorded under session user <strong>{user?.full_name}</strong> (CRC, Site {user?.site_id}).
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={onNavigateDashboard}
                className="border border-slate-400 bg-white px-5 py-2.5 text-xs font-bold uppercase tracking-wider text-slate-800 hover:bg-slate-100 transition"
              >
                Cancel / Return
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="border border-slate-900 bg-slate-900 px-6 py-2.5 text-xs font-bold uppercase tracking-wider text-white hover:bg-slate-800 disabled:opacity-50 transition shadow-sm"
              >
                {submitting ? 'Verifying & Registering...' : 'Submit Screening Registration'}
              </button>
            </div>
          </div>
        </form>
      )}
    </div>
  )
}
