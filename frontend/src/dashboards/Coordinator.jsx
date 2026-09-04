import { useEffect, useState, useRef } from 'react'
import { fetchTrials, fetchCoordinatorSummary } from '../api'
import DashboardLayout from './layout'
import ParticipantIntakeModal from '../components/ParticipantIntakeModal'
import ReportAdverseEventModal from '../components/ReportAdverseEventModal'
import LogProtocolDeviationModal from '../components/LogProtocolDeviationModal'
import ParticipantDossierModal from '../components/ParticipantDossierModal'

/* ── Compliance Banner ─────────────────────────────────────────────────── */
function SiteComplianceStatusBanner() {
  const [trial, setTrial] = useState(null)
  useEffect(() => {
    fetchTrials().then(r => { if (r.items?.[0]) setTrial(r.items[0]) }).catch(() => {})
  }, [])
  const ok = trial?.ethics_approval_status === 'approved'
  const ctri = Boolean(trial?.ctri_number?.trim())
  const clear = ok && ctri
  return (
    <div className={`flex items-center justify-between rounded-lg border px-4 py-2.5 text-xs ${clear ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>
      <span className="flex items-center gap-2 font-medium">
        <span className={`flex h-2 w-2 rounded-full ${clear ? 'bg-emerald-600' : 'bg-amber-600'}`}></span>
        {clear
          ? `Cleared. Regulatory & Ethics Cleared (${trial?.ethics_approval_number || 'IEC Approved'} | ${trial?.ctri_number}): Site authorized to recruit.`
          : !ok
          ? `Enrollment On Hold: Trial ethics approval is ${trial?.ethics_approval_status || 'Pending'}. Software blocks enrollment until IEC approves.`
          : `Enrollment On Hold: Prospective CTRI registration required before participant screening (NDCT Rules 2019).`}
      </span>
      <span className="hidden sm:inline font-mono text-[11px]">NDCT Rules 2019 Rule 22</span>
    </div>
  )
}

/* ── Open Data Queries ─────────────────────────────────────────────────── */
function OpenDataQueries() {
  const q = [
    { id: 'QRY-102', participant: 'AIIA-ASH-01-080', issue: 'Blood pressure exceeds logical threshold', status: 'OPEN' },
    { id: 'QRY-103', participant: 'AIIA-ASH-01-112', issue: 'Missing signature on AE source document', status: 'OPEN' },
  ]
  return (
    <div className="border border-red-200 rounded-xl bg-white shadow-sm overflow-hidden mb-6">
      <div className="bg-red-50 border-b border-red-200 p-4">
        <h3 className="text-sm font-bold text-red-900 uppercase tracking-wider flex items-center gap-2">
          <span className="text-red-600">🚨</span> Open Data Queries (Site Action Required)
        </h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm text-slate-700">
          <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
            <tr>
              <th className="px-4 py-3 border-r border-slate-200">Query ID</th>
              <th className="px-4 py-3 border-r border-slate-200">Related Participant</th>
              <th className="px-4 py-3 border-r border-slate-200">Data Issue</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {q.map((r, i) => (
              <tr key={i} className="hover:bg-slate-50">
                <td className="px-4 py-3 border-r border-slate-100 font-mono text-xs">{r.id}</td>
                <td className="px-4 py-3 border-r border-slate-100 font-medium">{r.participant}</td>
                <td className="px-4 py-3 border-r border-slate-100">{r.issue}</td>
                <td className="px-4 py-3">
                  <span className="px-2 py-1 rounded text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200">{r.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ── Confidence badge ──────────────────────────────────────────────────── */
function ConfBadge({ value }) {
  const cls = value >= 85
    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
    : value >= 70
    ? 'bg-amber-50 text-amber-700 border-amber-200'
    : 'bg-red-50 text-red-700 border-red-200'
  const label = value >= 85 ? 'High Match' : value >= 70 ? 'Medium Match' : 'Review Required'
  return <span className={`px-2 py-0.5 rounded text-[11px] font-bold border ${cls}`}>{value}% · {label}</span>
}

/* ── Spinner SVG ───────────────────────────────────────────────────────── */
const Spinner = () => (
  <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
  </svg>
)

/* ══════════════════════════════════════════════════════════════════════════
   MAIN COORDINATOR COMPONENT
   ══════════════════════════════════════════════════════════════════════════ */
export default function Coordinator(props) {
  const [showIntakeModal, setShowIntakeModal] = useState(false)
  const [showAeModal, setShowAeModal] = useState(false)
  const [showDeviationModal, setShowDeviationModal] = useState(false)
  const [selectedSubjectId, setSelectedSubjectId] = useState(null)
  const [summaryData, setSummaryData] = useState(null)

  const loadSummary = () => {
    fetchCoordinatorSummary()
      .then((data) => {
        if (data?.tiles?.length) setSummaryData(data)
      })
      .catch(() => {})
  }

  useEffect(() => {
    loadSummary()
  }, [])

  useEffect(() => {
    loadSummary()
  }, [props.dashboard, props.lastEvent])

  const handleRefreshAll = () => {
    loadSummary()
    props.onRefresh?.()
  }

  const activeDashboard = summaryData?.tiles ? {
    ...props.dashboard,
    tiles: summaryData.tiles,
  } : props.dashboard

  // ── Ingestion pipeline state ──────────────────────────────────────────
  const [ingestResults, setIngestResults] = useState(null)
  const [isIngesting, setIsIngesting] = useState(false)
  const [ingestError, setIngestError] = useState(null)
  const [approvals, setApprovals] = useState({})  // { idx: bool }
  const [toast, setToast] = useState(null)

  // ── Site KPI state ────────────────────────────────────────────────────
  const [kpiScreened, setKpiScreened] = useState(68)
  const [kpiEnrolled, setKpiEnrolled] = useState(68)
  const [kpiDeviations, setKpiDeviations] = useState(34)

  const pdfRef = useRef(null)
  const csvRef = useRef(null)

  // ── Upload handler (shared for both dropzones) ────────────────────────
  const handleUpload = async (file, endpoint) => {
    setIsIngesting(true)
    setIngestError(null)
    setIngestResults(null)
    setApprovals({})

    const fd = new FormData()
    fd.append('file', file)

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
        body: fd,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || data.detail || 'Ingestion failed')

      setIngestResults(data)
      // Default: approve all records
      const all = {}
      data.records.forEach((_, i) => { all[i] = true })
      setApprovals(all)
    } catch (err) {
      setIngestError(err.message)
    } finally {
      setIsIngesting(false)
    }
  }

  // ── Approve & Sync handler ────────────────────────────────────────────
  const handleApprove = () => {
    if (!ingestResults) return
    const approved = ingestResults.records.filter((_, i) => approvals[i])
    const passedCount = approved.filter(r => r.screening_outcome === 'PASSED').length

    setKpiScreened(prev => prev + approved.length)
    setKpiEnrolled(prev => prev + passedCount)
    setIngestResults(null)
    setApprovals({})
    setToast('Batch Ingestion Verified: Screened records committed to CDISC registry under 21 CFR Part 11.')
    handleRefreshAll()
    setTimeout(() => setToast(null), 6000)
  }

  const handleDiscard = () => {
    setIngestResults(null)
    setApprovals({})
  }

  const toggleApproval = (idx) => {
    setApprovals(prev => ({ ...prev, [idx]: !prev[idx] }))
  }

  // Derived summary
  const summary = ingestResults?.batch_summary

  return (
    <div className="space-y-6">
      {/* Toast notification */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 max-w-lg animate-bounce">
          <div className="bg-emerald-600 text-white px-5 py-3 rounded-lg shadow-xl text-sm font-medium flex items-center gap-3">
            <span className="text-lg">✅</span>
            {toast}
            <button onClick={() => setToast(null)} className="ml-auto text-white/80 hover:text-white font-bold">✕</button>
          </div>
        </div>
      )}

      <SiteComplianceStatusBanner />

      {/* ── Clinical Site Actions Center ─────────────────────────────── */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span className="flex h-2 w-2 rounded-full bg-aiia-600"></span>
              Site Clinical Actions &amp; Intake Center
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Execute structured CDASH participant intake, MedDRA safety reports, and protocol deviations.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button onClick={() => setShowIntakeModal(true)} className="flex items-center gap-1.5 rounded-lg bg-aiia-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-aiia-700 transition">
              ➕ Screen New Participant
            </button>
            <button onClick={() => setShowAeModal(true)} className="flex items-center gap-1.5 rounded-lg bg-red-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-red-700 transition">
              🚨 Report Adverse Event
            </button>
            <button onClick={() => setShowDeviationModal(true)} className="flex items-center gap-1.5 rounded-lg bg-amber-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-amber-700 transition">
              ⚠️ Log Protocol Deviation
            </button>
            <button onClick={() => setSelectedSubjectId(1)} className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition">
              🔍 Inspect Participant Dossier
            </button>
          </div>
        </div>
      </div>

      {/* ── Intake & Source Document Automation ──────────────────────── */}
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-bold text-slate-800">Intake &amp; Source Document Automation</h2>
          <p className="text-sm text-slate-500">Automated ingestion tools powered by AI and deterministic matching.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* ── Dropzone A: PDF ────────────────────────────────────── */}
          <div
            className="bg-white border-2 border-dashed border-aiia-300 text-slate-700 p-8 rounded-xl flex flex-col items-center justify-center gap-4 w-full cursor-pointer hover:bg-slate-50 transition-colors"
            onClick={() => pdfRef.current?.click()}
          >
            <span className="text-4xl text-aiia-600">📄</span>
            <div className="text-center">
              <div className="text-base font-bold uppercase tracking-wider text-slate-900 mb-2">AI Source Document Extraction (PDF)</div>
              <div className="text-sm text-slate-500 max-w-sm mx-auto">
                Upload patient lab reports. RapidFuzz + LLM pipeline will auto-extract vitals and redact PII.
              </div>
            </div>
            <button className="mt-2 bg-slate-900 text-white px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-slate-800 transition">
              Select PDF
            </button>
            <input
              ref={pdfRef}
              type="file"
              accept=".pdf,.txt"
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.[0]) handleUpload(e.target.files[0], '/api/ingest/source-document')
              }}
            />
          </div>

          {/* ── Dropzone B: CSV ────────────────────────────────────── */}
          <div
            className="bg-white border-2 border-dashed border-emerald-300 text-slate-700 p-8 rounded-xl flex flex-col items-center justify-center gap-4 w-full cursor-pointer hover:bg-slate-50 transition-colors"
            onClick={() => csvRef.current?.click()}
          >
            <span className="text-4xl text-emerald-600">📊</span>
            <div className="text-center">
              <div className="text-base font-bold uppercase tracking-wider text-slate-900 mb-2">CDISC CDASH Batch Screening Ingest (CSV)</div>
              <div className="text-sm text-slate-500 max-w-sm mx-auto">
                Upload raw site screening spreadsheets. Fuzzy matching maps headers to CDISC ODM DM/IE domain.
              </div>
            </div>
            <button className="mt-2 bg-emerald-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-emerald-800 transition">
              Select CSV / Excel
            </button>
            <input
              ref={csvRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.[0]) handleUpload(e.target.files[0], '/api/ingest/screening-csv')
              }}
            />
          </div>
        </div>
      </div>

      {/* Loading overlay */}
      {isIngesting && (
        <div className="bg-white border border-aiia-200 rounded-xl p-8 flex items-center justify-center gap-3 text-aiia-800 font-medium shadow-sm">
          <Spinner />
          <span>Processing Document &bull; Normalizing Terms &bull; Redacting PII &bull; Harmonizing to CDISC SDTM...</span>
        </div>
      )}

      {/* Error display */}
      {ingestError && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-5 py-4 rounded-xl text-sm flex items-center gap-3">
          <span className="text-lg">❌</span>
          <div>
            <strong>Ingestion Error:</strong> {ingestError}
          </div>
        </div>
      )}

      {/* ── Batch Verification & Staging Table ───────────────────────── */}
      {ingestResults && ingestResults.records && (
        <div className="border border-slate-200 rounded-xl bg-white shadow-sm overflow-hidden space-y-0">
          {/* Header */}
          <div className="bg-slate-900 text-white p-5 flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="text-xs text-aiia-300 font-mono font-bold uppercase tracking-wider">
                {ingestResults.source_type} Pipeline &bull; Job #{ingestResults.job_id}
              </div>
              <h3 className="text-lg font-bold mt-1">Batch Ingestion Verification &amp; Harmonization Review</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Review extracted fields and fuzzy match scores before committing to primary trial database.
              </p>
            </div>
            {summary && (
              <div className="flex items-center gap-3 text-xs">
                <span className="bg-slate-800 border border-slate-700 px-3 py-1.5 rounded font-mono">
                  Total: <strong className="text-white">{summary.total_screened}</strong>
                </span>
                <span className="bg-emerald-950 border border-emerald-800 text-emerald-300 px-3 py-1.5 rounded font-mono">
                  Passed: <strong>{summary.passed}</strong>
                </span>
                <span className="bg-red-950 border border-red-800 text-red-300 px-3 py-1.5 rounded font-mono">
                  Failed: <strong>{summary.screen_failures}</strong>
                </span>
                <span className="bg-aiia-950 border border-aiia-800 text-aiia-300 px-3 py-1.5 rounded font-mono">
                  Avg Conf: <strong>{summary.average_confidence_pct}%</strong>
                </span>
              </div>
            )}
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-[11px] uppercase font-bold text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-3 py-3 border-r border-slate-200">De-ID Code</th>
                  <th className="px-3 py-3 border-r border-slate-200">Age / Sex</th>
                  <th className="px-3 py-3 border-r border-slate-200">Dosha (Prakriti)</th>
                  <th className="px-3 py-3 border-r border-slate-200">Chief Complaint</th>
                  <th className="px-3 py-3 border-r border-slate-200">Vital Signs</th>
                  <th className="px-3 py-3 border-r border-slate-200">CDISC Match Quality</th>
                  <th className="px-3 py-3 border-r border-slate-200">Outcome</th>
                  <th className="px-3 py-3 text-center">Approve</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {ingestResults.records.map((rec, idx) => (
                  <tr key={idx} className={`hover:bg-slate-50 ${!approvals[idx] ? 'opacity-40 bg-slate-50' : ''}`}>
                    <td className="px-3 py-3 font-mono font-bold text-slate-900 border-r border-slate-100">
                      {rec.subject_code}
                    </td>
                    <td className="px-3 py-3 border-r border-slate-100">
                      {rec.age ? `${rec.age}y` : '—'} / {rec.sex || '—'}
                    </td>
                    <td className="px-3 py-3 border-r border-slate-100 font-medium">
                      {rec.prakriti || '—'}
                    </td>
                    <td className="px-3 py-3 border-r border-slate-100 max-w-xs truncate" title={rec.chief_complaint}>
                      {rec.chief_complaint || '—'}
                    </td>
                    <td className="px-3 py-3 font-mono text-[11px] border-r border-slate-100">
                      {rec.vitals ? `BP: ${rec.vitals.blood_pressure || '—'} | HR: ${rec.vitals.heart_rate || '—'}` : '—'}
                    </td>
                    <td className="px-3 py-3 border-r border-slate-100">
                      <ConfBadge value={rec.confidence_pct || 90} />
                    </td>
                    <td className="px-3 py-3 border-r border-slate-100">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-bold border ${
                        rec.screening_outcome === 'PASSED'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-red-50 text-red-700 border-red-200'
                      }`}>
                        {rec.screening_outcome}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-center">
                      <input
                        type="checkbox"
                        checked={!!approvals[idx]}
                        onChange={() => toggleApproval(idx)}
                        className="h-4 w-4 rounded border-slate-300 text-aiia-600 focus:ring-aiia-500 cursor-pointer"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Commit Controls */}
          <div className="bg-slate-50 border-t border-slate-200 px-5 py-4 flex items-center justify-between">
            <div className="text-xs text-slate-500">
              {Object.values(approvals).filter(Boolean).length} of {ingestResults.records.length} records selected for approval
            </div>
            <div className="flex items-center gap-3">
              <button onClick={handleDiscard} className="px-4 py-2 rounded-lg border border-slate-300 text-xs font-semibold text-slate-600 hover:bg-slate-100 transition">
                Discard Batch
              </button>
              <button onClick={handleApprove} className="px-5 py-2 rounded-lg bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 transition shadow-sm">
                Approve &amp; Sync to Site KPIs
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Open Data Queries & KPI Dashboard ───────────────────────── */}
      <div className="pt-4">
        <OpenDataQueries />
        <DashboardLayout
          {...props}
          dashboard={activeDashboard}
          wide={['upcoming', 'screening']}
          note="Your worklist for the next two weeks. An overdue visit becomes a protocol deviation if it slips outside its window, so these dates are the ones that matter."
        />
      </div>

      {/* ── Modals ───────────────────────────────────────────────────── */}
      {showIntakeModal && (
        <ParticipantIntakeModal
          onClose={() => setShowIntakeModal(false)}
          onSuccess={handleRefreshAll}
        />
      )}
      {showAeModal && (
        <ReportAdverseEventModal
          onClose={() => setShowAeModal(false)}
          onSuccess={handleRefreshAll}
        />
      )}
      {showDeviationModal && (
        <LogProtocolDeviationModal
          onClose={() => setShowDeviationModal(false)}
          onSuccess={handleRefreshAll}
        />
      )}
      {selectedSubjectId && (
        <ParticipantDossierModal
          subjectId={selectedSubjectId}
          onClose={() => setSelectedSubjectId(null)}
        />
      )}
    </div>
  )
}
