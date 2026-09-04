// Ethics Committee Dashboard
// Official Government Portal Aesthetic (Ministry of AYUSH / Central Ethics Committee for Ayurveda Research)
// Implements NDCT Rules 2019, GCP-ASU, and permanent individual SAE adjudication persistence.

import { useEffect, useState } from 'react'
import { fetchTrials, updateEthicsApproval, fetchEthicsDocket, submitSaeEthicsDecision } from '../api'
import DashboardLayout from './layout'
import SaeEthicsReviewModal from '../components/SaeEthicsReviewModal'

function GovernmentPortalHeader({ trials, selectedTrialId, onSelectTrial, trial }) {
  return (
    <div className="border-2 border-slate-800 bg-slate-900 text-white p-4 sm:p-5 shadow-sm space-y-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center border-2 border-amber-400 bg-slate-800 text-2xl font-bold text-amber-400">
            🏛️
          </div>
          <div>
            <div className="text-[11px] font-bold tracking-widest text-amber-400 uppercase">
              GOVERNMENT OF INDIA &bull; MINISTRY OF AYUSH
            </div>
            <h1 className="text-base sm:text-lg font-bold uppercase tracking-wide text-white font-serif">
              Institutional Ethics Committee (IEC) &bull; Clinical Safety &amp; Protocol Oversight
            </h1>
            <p className="text-xs text-slate-300 font-mono mt-0.5">
              Statutory Gate: NDCT Rules 2019 (Rule 22 &amp; 42) &bull; GCP-ASU &bull; CDSCO Notified Committee
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 border-t md:border-t-0 md:border-l border-slate-700 pt-3 md:pt-0 md:pl-4">
          <div className="text-left md:text-right">
            <span className="text-[10px] text-slate-400 uppercase block font-semibold tracking-wider">
              Committee Scope
            </span>
            <span className="text-xs font-mono font-bold text-emerald-400">
              Multi-Centric Trial Jurisdiction
            </span>
          </div>
          <span className="inline-block border border-purple-400 bg-purple-950/80 px-2.5 py-1 text-[11px] font-mono text-purple-200 uppercase font-semibold">
            Blinded Ethics Mode
          </span>
        </div>
      </div>

      {/* Protocol Selection & Gate Selector */}
      <div className="border-t border-slate-700 pt-3 flex flex-wrap items-center justify-between gap-3 bg-slate-950/60 -mx-4 -mb-4 p-3.5">
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-xs font-bold uppercase tracking-wider text-amber-300 whitespace-nowrap">
            Select Protocol for IEC Review &amp; Clearance:
          </label>
          <select
            value={selectedTrialId || ''}
            onChange={(e) => onSelectTrial(Number(e.target.value))}
            className="border-2 border-amber-400 bg-slate-800 text-white px-3 py-1.5 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-amber-300 max-w-md"
          >
            {trials.map((t) => (
              <option key={t.id} value={t.id}>
                {t.protocol_number}: {t.short_title || t.title} &mdash; [{t.ethics_approval_status ? t.ethics_approval_status.toUpperCase() : 'PENDING'}]
              </option>
            ))}
          </select>
        </div>

        {trial && (
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-300">Current Status:</span>
            <span
              className={`px-2.5 py-0.5 text-xs font-bold uppercase border ${
                trial.ethics_approval_status === 'approved'
                  ? 'border-emerald-500 bg-emerald-950 text-emerald-300'
                  : 'border-rose-500 bg-rose-950 text-rose-300 animate-pulse'
              }`}
            >
              {trial.ethics_approval_status ? trial.ethics_approval_status.toUpperCase() : 'PENDING APPROVAL'}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

function ProtocolClearanceCard({ trial, onUpdated }) {
  const [status, setStatus] = useState('approved')
  const [approvalNumber, setApprovalNumber] = useState('')
  const [approvalDate, setApprovalDate] = useState('')
  const [validUntil, setValidUntil] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    if (trial) {
      setStatus(trial.ethics_approval_status || 'approved')
      setApprovalNumber(trial.ethics_approval_number || `IEC/AIIA/2026/${String(trial.id).padStart(3, '0')}`)
      setApprovalDate(trial.ethics_approval_date || new Date().toISOString().slice(0, 10))
      if (trial.ethics_approval_valid_until) {
        setValidUntil(trial.ethics_approval_valid_until)
      } else {
        const nextYear = new Date()
        nextYear.setFullYear(nextYear.getFullYear() + 1)
        setValidUntil(nextYear.toISOString().slice(0, 10))
      }
    }
  }, [trial])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!trial) return
    setSaving(true)
    setError('')
    setSuccess('')

    try {
      const payload = {
        ethics_approval_status: status,
        ethics_approval_number: status === 'approved' || status === 'expired' ? approvalNumber.trim() : null,
        ethics_approval_date: status === 'approved' || status === 'expired' ? approvalDate : null,
        ethics_approval_valid_until: status === 'approved' || status === 'expired' ? validUntil : null,
      }
      await updateEthicsApproval(trial.id, payload)
      setSuccess(`IEC Protocol Decision successfully recorded and broadcast! Status: ${status.toUpperCase()} for ${trial.protocol_number}`)
      onUpdated?.()
    } catch (err) {
      setError(err?.message || 'Failed to record protocol clearance')
    } finally {
      setSaving(false)
    }
  }

  if (!trial) {
    return (
      <div className="border-2 border-slate-400 bg-white p-6 text-center text-xs text-slate-500">
        Loading trial protocol...
      </div>
    )
  }

  const isApproved = trial.ethics_approval_status === 'approved'

  return (
    <div className="border-2 border-slate-400 bg-white shadow-sm p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b-2 border-slate-200 pb-3">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900 flex items-center gap-2">
            <span>📋</span>
            <span>Study Protocol Ethics Approval &amp; Clearance Certificate: {trial.protocol_number}</span>
          </h2>
          <p className="text-xs text-slate-500">
            Rule 22 Gate: Screening and participant intake remain blocked at all sites until this certificate is marked <strong>APPROVED</strong>.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-semibold uppercase">Current Status:</span>
          <span className={`px-2.5 py-0.5 text-xs font-bold uppercase border ${
            isApproved
              ? 'border-emerald-600 bg-emerald-50 text-emerald-800'
              : 'border-rose-600 bg-rose-50 text-rose-800'
          }`}>
            {trial.ethics_approval_status ? trial.ethics_approval_status.toUpperCase() : 'PENDING'}
          </span>
        </div>
      </div>

      {error && (
        <div className="border border-rose-400 bg-rose-50 p-3 text-xs font-medium text-rose-800">
          <strong>Error:</strong> {error}
        </div>
      )}

      {success && (
        <div className="border border-emerald-400 bg-emerald-50 p-3 text-xs font-medium text-emerald-800">
          <strong>Success:</strong> {success}
        </div>
      )}

      <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
            Committee Decision
          </label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="w-full rounded-none border-2 border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-900 focus:border-slate-700 focus:outline-none"
          >
            <option value="approved">APPROVED (Authorize Site Recruitment)</option>
            <option value="pending">PENDING (Block Enrollment)</option>
            <option value="rejected">REJECTED (Halt Study)</option>
            <option value="expired">EXPIRED (Requires Annual Renewal)</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
            IEC Approval Reference No.
          </label>
          <input
            type="text"
            required={status === 'approved' || status === 'expired'}
            disabled={status !== 'approved' && status !== 'expired'}
            value={approvalNumber}
            onChange={(e) => setApprovalNumber(e.target.value)}
            placeholder="e.g. IEC/AIIA/2026/042"
            className="w-full rounded-none border-2 border-slate-300 px-3 py-1.5 text-xs font-mono text-slate-900 focus:border-slate-700 focus:outline-none disabled:bg-slate-100"
          />
        </div>

        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
            Effective Date
          </label>
          <input
            type="date"
            required={status === 'approved' || status === 'expired'}
            disabled={status !== 'approved' && status !== 'expired'}
            value={approvalDate}
            onChange={(e) => setApprovalDate(e.target.value)}
            className="w-full rounded-none border-2 border-slate-300 px-3 py-1.5 text-xs font-mono text-slate-900 focus:border-slate-700 focus:outline-none disabled:bg-slate-100"
          />
        </div>

        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
            Validity / Annual Renewal Date
          </label>
          <input
            type="date"
            required={status === 'approved' || status === 'expired'}
            disabled={status !== 'approved' && status !== 'expired'}
            value={validUntil}
            onChange={(e) => setValidUntil(e.target.value)}
            className="w-full rounded-none border-2 border-slate-300 px-3 py-1.5 text-xs font-mono text-slate-900 focus:border-slate-700 focus:outline-none disabled:bg-slate-100"
          />
        </div>

        <div className="sm:col-span-2 lg:col-span-4 flex items-center justify-between pt-2 border-t border-slate-200">
          <span className="text-xs font-mono text-slate-600">
            Protocol: <strong>{trial.protocol_number}</strong> &bull; Registered Under Central Drugs Standard Control Organization (CDSCO)
          </span>
          <button
            type="submit"
            disabled={saving}
            className="rounded-none bg-slate-900 px-5 py-2 text-xs font-bold text-white hover:bg-slate-800 transition disabled:opacity-50"
          >
            {saving ? 'Updating Clearance...' : `⚖️ Record Official IEC Clearance (${status.toUpperCase()})`}
          </button>
        </div>
      </form>
    </div>
  )
}

function SaeAdjudicationDocket({ docket, onAdjudicate, onQuickDecision }) {
  const saes = docket?.saes || []

  return (
    <div className="border-2 border-slate-400 bg-white shadow-sm p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b-2 border-slate-200 pb-3">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900 flex items-center gap-2">
            <span>🚨</span>
            <span>Serious Adverse Event (SAE) Adjudication Docket</span>
          </h2>
          <p className="text-xs text-slate-500">
            NDCT Rules 2019 Rule 42: Every Serious Adverse Event must be reviewed and ruled on individually by the Ethics Committee.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="border border-slate-300 bg-slate-50 px-2.5 py-1 text-xs font-mono font-bold text-slate-800">
            {docket?.unreviewed_count || 0} Pending Review
          </span>
          <span className="border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs font-mono font-bold text-emerald-800">
            {docket?.reviewed_count || 0} Adjudicated
          </span>
        </div>
      </div>

      {saes.length === 0 ? (
        <div className="p-8 text-center text-xs font-medium text-slate-500 border border-dashed border-slate-300">
          ✅ No Serious Adverse Events registered for this trial protocol.
        </div>
      ) : (
        <div className="overflow-x-auto border border-slate-300">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b-2 border-slate-300 bg-slate-100 text-[11px] font-bold text-slate-800 uppercase tracking-wider">
                <th className="px-3 py-2.5 border-r border-slate-200">SAE Docket ID</th>
                <th className="px-3 py-2.5 border-r border-slate-200">Subject ID</th>
                <th className="px-3 py-2.5 border-r border-slate-200">Site / Institute</th>
                <th className="px-3 py-2.5 border-r border-slate-200">Verbatim Event Term</th>
                <th className="px-3 py-2.5 border-r border-slate-200">Seriousness Criterion</th>
                <th className="px-3 py-2.5 border-r border-slate-200">Onset Date</th>
                <th className="px-3 py-2.5 border-r border-slate-200">24h Regulatory Clock</th>
                <th className="px-3 py-2.5 border-r border-slate-200">Current IEC Ruling</th>
                <th className="px-3 py-2.5 text-center">Adjudication Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {saes.map((sae) => {
                const isPending = !sae.is_reviewed
                const isAccepted = sae.ec_decision === 'accepted'
                const isRejected = sae.ec_decision === 'rejected'

                return (
                  <tr
                    key={sae.id}
                    className={`hover:bg-slate-50/80 transition-colors ${
                      isPending ? 'bg-amber-50/40' : isRejected ? 'bg-rose-50/30' : ''
                    }`}
                  >
                    <td className="px-3 py-2.5 font-mono font-bold text-slate-900 border-r border-slate-200 whitespace-nowrap">
                      {sae.ae_number}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-slate-700 border-r border-slate-200 whitespace-nowrap">
                      {sae.subject_code}
                    </td>
                    <td className="px-3 py-2.5 text-slate-800 border-r border-slate-200">
                      <span className="font-mono text-[10px] text-slate-500 mr-1">[{sae.site_code}]</span>
                      {sae.site_name}
                    </td>
                    <td className="px-3 py-2.5 font-medium text-slate-900 border-r border-slate-200">
                      {sae.term_verbatim}
                    </td>
                    <td className="px-3 py-2.5 text-rose-700 font-semibold border-r border-slate-200">
                      {sae.seriousness_criteria}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-slate-600 border-r border-slate-200 whitespace-nowrap">
                      {sae.onset_date}
                    </td>
                    <td className="px-3 py-2.5 border-r border-slate-200 whitespace-nowrap">
                      <span className={`px-2 py-0.5 text-[10px] font-bold uppercase border ${
                        sae.clock_status === 'OVERDUE'
                          ? 'border-rose-400 bg-rose-100 text-rose-800'
                          : sae.clock_status === 'DUE_SOON'
                          ? 'border-amber-400 bg-amber-100 text-amber-800'
                          : 'border-emerald-400 bg-emerald-100 text-emerald-800'
                      }`}>
                        {sae.clock_label}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 border-r border-slate-200 whitespace-nowrap">
                      {isAccepted ? (
                        <div>
                          <span className="inline-block px-2 py-0.5 text-[11px] font-bold bg-emerald-100 border border-emerald-400 text-emerald-800">
                            ✅ CLEARED
                          </span>
                          <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                            {sae.ec_decision_date}
                          </div>
                        </div>
                      ) : isRejected ? (
                        <div>
                          <span className="inline-block px-2 py-0.5 text-[11px] font-bold bg-rose-100 border border-rose-400 text-rose-800">
                            ❌ REJECTED / SUSPENDED
                          </span>
                          <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                            {sae.ec_decision_date}
                          </div>
                        </div>
                      ) : (
                        <span className="inline-block px-2 py-0.5 text-[11px] font-bold bg-amber-100 border border-amber-400 text-amber-900">
                          ⏳ PENDING RULING
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-center whitespace-nowrap">
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          onClick={() => onQuickDecision(sae.id, 'accepted')}
                          title="Quick Accept / Clear Signal"
                          className="px-2 py-1 text-xs font-bold border border-emerald-600 bg-emerald-50 text-emerald-800 hover:bg-emerald-600 hover:text-white transition"
                        >
                          ✅ Accept
                        </button>
                        <button
                          onClick={() => onQuickDecision(sae.id, 'rejected')}
                          title="Quick Reject / Halt Subject"
                          className="px-2 py-1 text-xs font-bold border border-rose-600 bg-rose-50 text-rose-800 hover:bg-rose-600 hover:text-white transition"
                        >
                          ❌ Reject
                        </button>
                        <button
                          onClick={() => onAdjudicate(sae)}
                          title="Open Full Hearing &amp; Directive Modal"
                          className="px-2.5 py-1 text-xs font-bold border border-slate-700 bg-slate-800 text-white hover:bg-slate-900 transition"
                        >
                          ⚖️ Adjudicate
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default function Ethics(props) {
  const [trials, setTrials] = useState([])
  const [selectedTrialId, setSelectedTrialId] = useState(null)
  const [docket, setDocket] = useState({ unreviewed_count: 0, reviewed_count: 0, total_sae_count: 0, saes: [] })
  const [loading, setLoading] = useState(true)
  const [selectedSaeForReview, setSelectedSaeForReview] = useState(null)

  const loadData = async (trialIdToLoad) => {
    try {
      setLoading(true)
      const trialsRes = await fetchTrials()
      const items = trialsRes.items || []
      setTrials(items)
      
      const currentId = trialIdToLoad || selectedTrialId || items[0]?.id
      if (currentId && currentId !== selectedTrialId) {
        setSelectedTrialId(currentId)
      }

      const docketRes = await fetchEthicsDocket(currentId || undefined)
      if (docketRes) setDocket(docketRes)
    } catch (err) {
      console.error('Failed to load ethics data:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleSelectTrial = (id) => {
    setSelectedTrialId(id)
    loadData(id)
  }

  const handleQuickDecision = async (saeId, decision) => {
    try {
      await submitSaeEthicsDecision(saeId, {
        decision,
        notes: decision === 'accepted' ? 'Safety signal cleared upon initial committee review.' : 'Trial protocol halted for subject pending safety hearing.',
        decision_date: new Date().toISOString().slice(0, 10),
      })
      await loadData(selectedTrialId)
      props.onRefresh?.()
    } catch (err) {
      alert(err?.message || 'Failed to record decision')
    }
  }

  const handleReviewSuccess = async () => {
    setSelectedSaeForReview(null)
    await loadData(selectedTrialId)
    props.onRefresh?.()
  }

  const activeTrial = trials.find((t) => t.id === selectedTrialId) || trials[0]
  const unreviewedCount = docket?.unreviewed_count || 0
  const isPendingApproval = activeTrial && activeTrial.ethics_approval_status !== 'approved'

  return (
    <div className="space-y-6">
      {/* 1. Official Government Portal Header with Protocol Selector */}
      <GovernmentPortalHeader
        trials={trials}
        selectedTrialId={selectedTrialId}
        onSelectTrial={handleSelectTrial}
        trial={activeTrial}
      />

      {/* 2. Top Banner: Priority Protocol Clearance Notification when Pending */}
      {isPendingApproval ? (
        <div className="border-2 border-amber-500 bg-amber-50 p-4 sm:p-5 shadow-md">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center border border-amber-600 bg-amber-600 text-white text-xl font-bold">
                ⏳
              </span>
              <div>
                <h2 className="text-sm sm:text-base font-bold text-amber-950 uppercase tracking-wider">
                  Protocol Clearance Required: {activeTrial?.protocol_number} &mdash; IEC Review Status: {activeTrial?.ethics_approval_status?.toUpperCase() || 'PENDING'}
                </h2>
                <p className="text-xs text-amber-800 font-medium mt-0.5">
                  This clinical trial protocol is awaiting formal Ethics Committee review and approval under NDCT Rules 2019 Rule 22. Complete the certificate below to authorize multi-centric recruitment.
                </p>
              </div>
            </div>
            <a
              href="#protocol-clearance-section"
              className="rounded-none border-2 border-amber-800 bg-amber-700 px-4 py-2 text-xs font-bold text-white hover:bg-amber-800 transition whitespace-nowrap"
            >
              Review &amp; Approve Certificate &darr;
            </a>
          </div>
        </div>
      ) : unreviewedCount > 0 ? (
        <div className="border-2 border-rose-600 bg-rose-50 p-4 sm:p-5 shadow-md">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center border border-rose-600 bg-rose-600 text-white text-xl font-bold">
                🚨
              </span>
              <div>
                <h2 className="text-sm sm:text-base font-bold text-rose-950 uppercase tracking-wider">
                  Critical Safety Alert: {unreviewedCount} Serious Adverse Event(s) Awaiting Individual Adjudication
                </h2>
                <p className="text-xs text-rose-800 font-medium mt-0.5">
                  NDCT Rules 2019 Rule 42 requires independent committee rulings on each reported Serious Adverse Event.
                </p>
              </div>
            </div>
            <a
              href="#sae-docket-section"
              className="rounded-none border-2 border-rose-800 bg-rose-700 px-4 py-2 text-xs font-bold text-white hover:bg-rose-800 transition whitespace-nowrap"
            >
              Review SAE Docket &darr;
            </a>
          </div>
        </div>
      ) : (
        <div className="border-2 border-emerald-600 bg-emerald-50 p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center border border-emerald-600 bg-emerald-600 text-white text-base font-bold">
              ✓
            </span>
            <div>
              <h2 className="text-xs sm:text-sm font-bold text-emerald-950 uppercase tracking-wider">
                Protocol Active &amp; All Safety Signals Evaluated
              </h2>
              <p className="text-[11px] text-emerald-800 mt-0.5">
                Protocol <strong>{activeTrial?.protocol_number}</strong> is authorized for clinical recruitment under Certificate <code>{activeTrial?.ethics_approval_number || 'IEC Cleared'}</code>.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 3. Study Protocol Clearance Certificate Box */}
      <div id="protocol-clearance-section">
        <ProtocolClearanceCard trial={activeTrial} onUpdated={() => loadData(selectedTrialId)} />
      </div>

      {/* 4. SAE Adjudication Docket (Individual Accept/Reject) */}
      <div id="sae-docket-section">
        <SaeAdjudicationDocket
          docket={docket}
          onAdjudicate={(sae) => setSelectedSaeForReview(sae)}
          onQuickDecision={handleQuickDecision}
        />
      </div>

      {/* 5. Core Ethics Layout & Compliance Checklist */}
      <DashboardLayout
        {...props}
        wide={['sae_reporting', 'deviations']}
        note="Severity is how bad an event felt; seriousness is a regulatory category - death, hospitalisation, disability - that starts a reporting clock. Every SAE ruling is recorded in the permanent audit trail."
      />

      {/* Modal */}
      {selectedSaeForReview && (
        <SaeEthicsReviewModal
          sae={selectedSaeForReview}
          onClose={() => setSelectedSaeForReview(null)}
          onSuccess={handleReviewSuccess}
        />
      )}
    </div>
  )
}
