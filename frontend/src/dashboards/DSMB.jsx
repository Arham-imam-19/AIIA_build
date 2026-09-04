import { useEffect, useState } from 'react'
import DashboardLayout from './layout'
import { fetchTrials, fetchSites, submitDsmbDecision, fetchDsmbDecisions } from '../api'

export default function DSMB(props) {
  const [trials, setTrials] = useState([])
  const [selectedTrialId, setSelectedTrialId] = useState(null)
  const [sites, setSites] = useState([])
  const [selectedSiteId, setSelectedSiteId] = useState('')
  const [targetScope, setTargetScope] = useState('all') // 'all' | 'site'
  const [decision, setDecision] = useState('CONTINUE')
  const [notes, setNotes] = useState('Routine quarterly safety review completed. Risk-benefit balance remains favorable for trial continuation.')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [successNotice, setSuccessNotice] = useState(null)
  const [history, setHistory] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(false)

  // 1. Fetch available trials
  useEffect(() => {
    fetchTrials()
      .then((res) => {
        const items = res.items || res || []
        setTrials(items)
        if (items.length > 0 && !selectedTrialId) {
          setSelectedTrialId(items[0].id)
        }
      })
      .catch((err) => {
        console.error('Failed to load trials:', err)
      })
  }, [])

  // 2. Fetch sites & directives history when trial changes
  useEffect(() => {
    if (!selectedTrialId) return
    setError(null)
    setSuccessNotice(null)

    // Fetch sites for this trial
    fetchSites({ trial_id: selectedTrialId })
      .then((res) => {
        const siteItems = res.items || res || []
        setSites(siteItems)
        if (siteItems.length > 0) {
          setSelectedSiteId(siteItems[0].id)
        } else {
          setSelectedSiteId('')
        }
      })
      .catch(() => setSites([]))

    // Fetch past decisions
    loadHistory(selectedTrialId)
  }, [selectedTrialId])

  const loadHistory = (trialId) => {
    if (!trialId) return
    setLoadingHistory(true)
    fetchDsmbDecisions(trialId)
      .then((data) => setHistory(data || []))
      .catch(() => setHistory([]))
      .finally(() => setLoadingHistory(false))
  }

  const selectedTrial = trials.find(t => t.id === Number(selectedTrialId)) || trials[0]
  const targetSite = sites.find(s => s.id === Number(selectedSiteId))

  const handleDecisionChange = (newDecision) => {
    setDecision(newDecision)
    setError(null)
    if (newDecision === 'CONTINUE') {
      setNotes('Routine quarterly safety review completed. Adverse event incidence is within acceptable protocol limits. Continuation recommended without modification.')
    } else if (newDecision === 'MODIFY') {
      setNotes('Safety review identified emerging mild-to-moderate events. Recommend immediate protocol amendment: tighten renal/hepatic exclusion criteria and increase monitoring frequency.')
    } else if (newDecision === 'HALT') {
      setNotes('CRITICAL SAFETY DIRECTIVE: Expedited review reveals serious adverse events exceeding stopping boundary thresholds. Immediate suspension of screening and study medication administration required.')
    }
  }

  const applyTemplate = (templateText) => {
    setNotes(templateText)
  }

  const logDecision = async (e) => {
    e.preventDefault()
    if (!selectedTrial) {
      setError('Please select an active clinical trial protocol.')
      return
    }

    if (targetScope === 'site' && !selectedSiteId) {
      setError('Please select a specific hospital site for this directive.')
      return
    }

    if (!notes.trim()) {
      setError('Please provide board safety rationale and specific directives.')
      return
    }

    setSubmitting(true)
    setError(null)
    setSuccessNotice(null)

    try {
      const payload = {
        decision: decision,
        site_id: targetScope === 'site' ? Number(selectedSiteId) : null,
        notes: notes.trim(),
        directive_title: `DSMB ${decision} Directive`,
      }

      const trialIdToUse = selectedTrial?.id || (trials.length > 0 ? trials[0].id : 1)
      const res = await submitDsmbDecision(trialIdToUse, payload)
      setSuccessNotice({
        decision: decision,
        scope: res.scope || (targetScope === 'site' && targetSite ? `Site ${targetSite.site_code} (${targetSite.name})` : 'All Participating Sites'),
        piNotified: res.pi_notified || (targetScope === 'site' && targetSite ? targetSite.pi_name : 'All Principal Investigators'),
        message: res.message,
        id: res.id,
      })

      loadHistory(trialIdToUse)
      props.onRefresh?.()
    } catch (err) {
      setError(err.detail || err.message || 'Failed to submit DSMB official decision')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* DSMB Directive Logger Panel */}
      <section className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        {/* Header */}
        <div className="border-b border-slate-100 bg-slate-50/80 px-6 py-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex h-2.5 w-2.5 rounded-full bg-emerald-600 animate-pulse"></span>
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                Data & Safety Monitoring Board (DSMB) &middot; Statutory Safety Oversight
              </span>
            </div>
            <h2 className="text-base font-bold text-slate-900 mt-0.5">
              Trial Continuation Decision Logger
            </h2>
            <p className="text-xs text-slate-500">
              Formally log board determinations, issue site-specific safety directives, and notify Principal Investigators under ICH-GCP E6(R2).
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="rounded border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-800">
              ⚖️ Independent Safety Quorum
            </span>
          </div>
        </div>

        <form onSubmit={logDecision} className="p-6 space-y-5">
          {/* Error Message */}
          {error && (
            <div className="rounded-lg border border-rose-300 bg-rose-50 p-3.5 text-xs font-semibold text-rose-900 flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span>⚠️</span>
                <span>{error}</span>
              </span>
              <button type="button" onClick={() => setError(null)} className="text-rose-700 hover:text-rose-950 font-bold">✕</button>
            </div>
          )}

          {/* Success Banner */}
          {successNotice && (
            <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-4 text-xs text-emerald-950 shadow-xs">
              <div className="flex items-center justify-between mb-1.5">
                <span className="flex items-center gap-2 font-bold text-emerald-900">
                  <span className="text-base">✅</span>
                  <span>Board Determination Transmitted & Logged</span>
                </span>
                <button type="button" onClick={() => setSuccessNotice(null)} className="text-emerald-700 hover:text-emerald-950 font-bold">✕</button>
              </div>
              <p className="text-emerald-800 leading-relaxed">
                Decision <strong className="uppercase underline">{successNotice.decision}</strong> has been ratified into the 21 CFR Part 11 audit log.
                Target Scope: <strong>{successNotice.scope}</strong>.
              </p>
              <div className="mt-2 inline-flex items-center gap-1.5 rounded bg-white px-2.5 py-1 border border-emerald-200 text-[11px] font-semibold text-emerald-900">
                <span>📨 Direct Notification Dispatched to:</span>
                <span className="text-emerald-950 font-bold">{successNotice.piNotified}</span>
              </div>
            </div>
          )}

          {/* Step 1: Target Protocol Selector */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
              1. Select Clinical Trial Protocol
            </label>
            <select
              value={selectedTrialId || ''}
              onChange={(e) => setSelectedTrialId(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-900 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 shadow-xs"
            >
              {trials.map((t) => (
                <option key={t.id} value={t.id}>
                  [{t.protocol_number}] {t.short_title || t.title} &middot; Status: {t.status?.toUpperCase()} &middot; Phase: {t.phase?.replace('_', ' ').toUpperCase()}
                </option>
              ))}
            </select>
            {selectedTrial && (
              <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-slate-500 font-medium">
                <span>Protocol: <strong className="text-slate-800">{selectedTrial.protocol_number}</strong></span>
                <span>&bull;</span>
                <span>Status: <strong className="text-slate-800 uppercase">{selectedTrial.status}</strong></span>
                <span>&bull;</span>
                <span>CTRI: <strong className="text-slate-800">{selectedTrial.ctri_number || 'Pending'}</strong></span>
                <span>&bull;</span>
                <span>Target Enrollment: <strong className="text-slate-800">{selectedTrial.target_enrollment} participants</strong></span>
              </div>
            )}
          </div>

          {/* Step 2: Board Decision Selection (3 Distinct Cards) */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
              2. Select Board Continuation Determination
            </label>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {/* Option 1: Continue Trial */}
              <label
                onClick={() => handleDecisionChange('CONTINUE')}
                className={`relative flex flex-col p-4 rounded-xl border cursor-pointer transition shadow-xs ${
                  decision === 'CONTINUE'
                    ? 'border-emerald-600 bg-emerald-50/50 ring-1 ring-emerald-600'
                    : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">🛡️</span>
                    <span className="font-bold text-xs text-emerald-950">Continue Trial</span>
                  </div>
                  <input
                    type="radio"
                    name="decision"
                    value="CONTINUE"
                    checked={decision === 'CONTINUE'}
                    onChange={() => handleDecisionChange('CONTINUE')}
                    className="h-4 w-4 text-emerald-600 focus:ring-emerald-500 border-slate-300"
                  />
                </div>
                <p className="text-[11px] text-slate-600 leading-relaxed">
                  Aggregated safety parameters within acceptable bounds. Unconditional continuation of recruitment & treatment.
                </p>
                <div className="mt-3 text-[10px] font-bold text-emerald-800 uppercase tracking-wider">
                  ✓ Safety Profile Favorable
                </div>
              </label>

              {/* Option 2: Modify Protocol */}
              <label
                onClick={() => handleDecisionChange('MODIFY')}
                className={`relative flex flex-col p-4 rounded-xl border cursor-pointer transition shadow-xs ${
                  decision === 'MODIFY'
                    ? 'border-amber-600 bg-amber-50/50 ring-1 ring-amber-600'
                    : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">⚠️</span>
                    <span className="font-bold text-xs text-amber-950">Modify Protocol</span>
                  </div>
                  <input
                    type="radio"
                    name="decision"
                    value="MODIFY"
                    checked={decision === 'MODIFY'}
                    onChange={() => handleDecisionChange('MODIFY')}
                    className="h-4 w-4 text-amber-600 focus:ring-amber-500 border-slate-300"
                  />
                </div>
                <p className="text-[11px] text-slate-600 leading-relaxed">
                  Emerging safety signals require protocol amendment, dose adjustment, or screening criteria tightening.
                </p>
                <div className="mt-3 text-[10px] font-bold text-amber-800 uppercase tracking-wider">
                  ⚠️ Action Directives Required
                </div>
              </label>

              {/* Option 3: Halt Trial (Emergency) */}
              <label
                onClick={() => handleDecisionChange('HALT')}
                className={`relative flex flex-col p-4 rounded-xl border cursor-pointer transition shadow-xs ${
                  decision === 'HALT'
                    ? 'border-rose-600 bg-rose-50/60 ring-1 ring-rose-600'
                    : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">🚨</span>
                    <span className="font-bold text-xs text-rose-950">Halt Trial (Emergency)</span>
                  </div>
                  <input
                    type="radio"
                    name="decision"
                    value="HALT"
                    checked={decision === 'HALT'}
                    onChange={() => handleDecisionChange('HALT')}
                    className="h-4 w-4 text-rose-600 focus:ring-rose-500 border-slate-300"
                  />
                </div>
                <p className="text-[11px] text-slate-600 leading-relaxed">
                  Severe safety risks or cluster SAEs detected. Immediate suspension of study activities to protect patient safety.
                </p>
                <div className="mt-3 text-[10px] font-bold text-rose-800 uppercase tracking-wider">
                  🛑 Immediate Statutory Pause
                </div>
              </label>
            </div>
          </div>

          {/* Step 3: Target Site Scope Selector */}
          <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700">
                3. Target Site Scope &amp; Investigator Notification
              </label>
              <span className="text-[11px] text-slate-500">Specify jurisdiction of this determination</span>
            </div>

            {/* Scope Radio Options */}
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-xs font-semibold text-slate-800 cursor-pointer">
                <input
                  type="radio"
                  name="targetScope"
                  value="all"
                  checked={targetScope === 'all'}
                  onChange={() => setTargetScope('all')}
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300"
                />
                <span>🌐 Entire Trial &mdash; All Participating Sites (Trial-Wide Directive)</span>
              </label>

              <label className="flex items-center gap-2 text-xs font-semibold text-slate-800 cursor-pointer">
                <input
                  type="radio"
                  name="targetScope"
                  value="site"
                  checked={targetScope === 'site'}
                  onChange={() => setTargetScope('site')}
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300"
                />
                <span>🏥 Specific Participating Hospital / Institute Site</span>
              </label>
            </div>

            {/* Specific Site Dropdown & Detail Card */}
            {targetScope === 'site' && (
              <div className="pt-2 space-y-3">
                <div className="max-w-xl">
                  <label className="block text-[11px] font-bold uppercase text-slate-600 mb-1">
                    Select Participating Center:
                  </label>
                  <select
                    value={selectedSiteId}
                    onChange={(e) => setSelectedSiteId(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-900 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 shadow-xs"
                  >
                    {sites.length === 0 && <option value="">No sites registered for this trial</option>}
                    {sites.map((s) => (
                      <option key={s.id} value={s.id}>
                        [Site {s.site_code}] {s.name} ({s.city}, {s.state}) &middot; PI: {s.pi_name}
                      </option>
                    ))}
                  </select>
                </div>

                {targetSite && (
                  <div className="rounded-lg border border-indigo-200 bg-white p-3.5 text-xs shadow-xs">
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2">
                      <span className="font-bold text-slate-900">
                        Site {targetSite.site_code}: {targetSite.name}
                      </span>
                      <span className="rounded bg-indigo-50 px-2 py-0.5 font-mono text-[10px] font-bold text-indigo-700 uppercase">
                        Status: {targetSite.status}
                      </span>
                    </div>

                    <div className="mt-2.5 grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                      <div>
                        <span className="text-slate-500 block">Designated Principal Investigator:</span>
                        <strong className="text-slate-900">{targetSite.pi_name}</strong>
                        {targetSite.pi_email && (
                          <span className="text-slate-500 block text-[10px] font-mono">{targetSite.pi_email}</span>
                        )}
                      </div>
                      <div>
                        <span className="text-slate-500 block">Center Location:</span>
                        <span className="text-slate-800 font-medium">{targetSite.city}, {targetSite.state}, {targetSite.country}</span>
                      </div>
                    </div>

                    <div className="mt-2.5 rounded bg-amber-50 border border-amber-200 p-2 text-[11px] text-amber-900 flex items-center gap-1.5">
                      <span>📨</span>
                      <span>
                        <strong>Notification Target:</strong> This directive will be delivered straight to <strong>{targetSite.pi_name}</strong> on their Principal Investigator portal with statutory acknowledgment requested.
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Step 4: Board Directives & Safety Rationale */}
          <div>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700">
                4. Safety Board Directives &amp; Clinical Rationale
              </label>
              <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                <span className="text-slate-400">Quick Directives:</span>
                <button
                  type="button"
                  onClick={() => applyTemplate('Routine safety review concluded. Participant safety parameters acceptable. Continue protocol as written.')}
                  className="rounded border border-slate-200 bg-white hover:bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700 shadow-2xs"
                >
                  Clearance
                </button>
                <button
                  type="button"
                  onClick={() => applyTemplate('Protocol safety amendment ordered: tighten baseline hepatic inclusion criteria and implement mandatory post-dose 2-hour monitoring.')}
                  className="rounded border border-slate-200 bg-white hover:bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700 shadow-2xs"
                >
                  Screening Adjustment
                </button>
                <button
                  type="button"
                  onClick={() => applyTemplate('Urgent safety hold: halt participant intake at this site immediately pending adjudication of serious adverse event signals.')}
                  className="rounded border border-slate-200 bg-white hover:bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700 shadow-2xs"
                >
                  Recruitment Pause
                </button>
              </div>
            </div>

            <textarea
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Enter comprehensive clinical directives, required protocol amendments, or safety rationale for the investigator..."
              className="w-full rounded-lg border border-slate-300 p-3 text-xs font-medium text-slate-900 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 shadow-xs"
            />
          </div>

          {/* Submit Action */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100">
            <span className="text-[11px] text-slate-500">
              Action is timestamped and permanently recorded in compliance with 21 CFR Part 11.
            </span>
            <button
              type="submit"
              disabled={submitting}
              className={`inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-xs font-bold text-white shadow-sm transition disabled:opacity-50 cursor-pointer ${
                decision === 'HALT'
                  ? 'bg-rose-700 hover:bg-rose-800'
                  : decision === 'MODIFY'
                  ? 'bg-amber-700 hover:bg-amber-800'
                  : 'bg-indigo-700 hover:bg-indigo-800'
              }`}
            >
              <span>{decision === 'HALT' ? '🚨' : decision === 'MODIFY' ? '📝' : '🛡️'}</span>
              <span>{submitting ? 'Submitting & Transmitting Directive…' : `Submit Official Decision: ${decision}`}</span>
            </button>
          </div>
        </form>
      </section>

      {/* Directives History & PI Acknowledgment Audit Table */}
      {history.length > 0 && (
        <section className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="border-b border-slate-100 bg-slate-50/70 px-6 py-3.5 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-base">📋</span>
              <div>
                <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                  Recent Board Directives &amp; PI Acknowledgment Records
                </h3>
                <p className="text-[11px] text-slate-500">
                  Real-time log of issued safety determinations and investigator responses for this protocol
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => loadHistory(selectedTrialId)}
              className="text-[11px] font-semibold text-indigo-700 hover:text-indigo-900"
            >
              {loadingHistory ? 'Refreshing…' : '↻ Refresh Log'}
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="border-b border-slate-200 bg-slate-50/90 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-5 py-3">Determination</th>
                  <th className="px-5 py-3">Target Scope &amp; Site</th>
                  <th className="px-5 py-3">Principal Investigator</th>
                  <th className="px-5 py-3">Directives &amp; Board Notes</th>
                  <th className="px-5 py-3">Date Issued</th>
                  <th className="px-5 py-3">PI Acknowledgment</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-xs">
                {history.map((h) => (
                  <tr key={h.id} className="hover:bg-slate-50/50">
                    <td className="px-5 py-3 whitespace-nowrap">
                      <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold uppercase ${
                        h.decision === 'CONTINUE'
                          ? 'bg-emerald-100 text-emerald-800'
                          : h.decision === 'MODIFY'
                          ? 'bg-amber-100 text-amber-900'
                          : 'bg-rose-100 text-rose-900'
                      }`}>
                        <span>{h.decision === 'CONTINUE' ? '✓' : h.decision === 'MODIFY' ? '⚠️' : '🛑'}</span>
                        <span>{h.decision}</span>
                      </span>
                    </td>
                    <td className="px-5 py-3 whitespace-nowrap">
                      <span className="font-semibold text-slate-800">
                        {h.site_name || 'All Participating Sites'}
                      </span>
                      {h.site_code && (
                        <span className="text-[10px] text-slate-400 block font-mono">Site Code: {h.site_code}</span>
                      )}
                    </td>
                    <td className="px-5 py-3 whitespace-nowrap">
                      <span className="font-semibold text-slate-800">{h.pi_name || 'All PIs'}</span>
                    </td>
                    <td className="px-5 py-3">
                      <div className="max-w-xs line-clamp-2 text-slate-700 text-[11px]" title={h.notes}>
                        {h.notes}
                      </div>
                    </td>
                    <td className="px-5 py-3 whitespace-nowrap text-[11px] font-mono text-slate-500">
                      {h.created_at ? new Date(h.created_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-5 py-3 whitespace-nowrap">
                      {h.is_acknowledged ? (
                        <div className="flex flex-col items-start">
                          <span className="inline-flex items-center gap-1 text-emerald-700 font-bold text-[11px]">
                            <span>✅</span>
                            <span>Acknowledged</span>
                          </span>
                          <span className="text-[10px] text-slate-400 font-mono">
                            {h.acknowledged_by_name || 'Principal Investigator'}
                          </span>
                        </div>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded bg-amber-50 border border-amber-200 px-2 py-0.5 text-[10px] font-bold text-amber-800">
                          <span>⏳</span>
                          <span>Pending PI Acknowledgment</span>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Underlying Dashboard Tiles and Analytics */}
      <DashboardLayout {...props} />
    </div>
  )
}
