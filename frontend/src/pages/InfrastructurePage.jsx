import { useEffect, useState } from 'react'
import { fetchSites, fetchTrials, resetTrialData } from '../api'
import CreateSiteModal from '../components/CreateSiteModal'
import CreateTrialModal from '../components/CreateTrialModal'

export default function InfrastructurePage({ onNavigateDashboard }) {
  const [trials, setTrials] = useState([])
  const [sites, setSites] = useState([])
  const [siteProtocolFilter, setSiteProtocolFilter] = useState('all')
  const [loading, setLoading] = useState(false)
  const [showTrialModal, setShowTrialModal] = useState(false)
  const [showSiteModal, setShowSiteModal] = useState(false)
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const [cleanSlateBusy, setCleanSlateBusy] = useState(false)
  const [cleanSlateResult, setCleanSlateResult] = useState(null)

  function loadData() {
    setLoading(true)
    Promise.all([fetchTrials(), fetchSites()])
      .then(([tRes, sRes]) => {
        setTrials(tRes.items || [])
        setSites(sRes.items || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
  }, [])

  // Trial lookup map for protocol numbers and titles
  const trialMap = Object.fromEntries(trials.map((t) => [t.id, t]))

  // Deduplicate and group physical research centers by site_code
  const distinctCentersMap = new Map()
  for (const s of sites) {
    if (!distinctCentersMap.has(s.site_code)) {
      distinctCentersMap.set(s.site_code, {
        ...s,
        total_target_enrollment: s.target_enrollment || 0,
        protocol_ids: s.trial_id ? [s.trial_id] : [],
      })
    } else {
      const entry = distinctCentersMap.get(s.site_code)
      entry.total_target_enrollment += (s.target_enrollment || 0)
      if (s.trial_id && !entry.protocol_ids.includes(s.trial_id)) {
        entry.protocol_ids.push(s.trial_id)
      }
      if (s.status === 'recruiting' || (s.status === 'activated' && entry.status !== 'recruiting')) {
        entry.status = s.status
      }
      if (!entry.pi_email && s.pi_email) entry.pi_email = s.pi_email
      if (!entry.contact_phone && s.contact_phone) entry.contact_phone = s.contact_phone
    }
  }
  const distinctCenters = Array.from(distinctCentersMap.values())

  // Sites to display based on selected protocol scope
  const displaySites = siteProtocolFilter === 'all'
    ? distinctCenters
    : sites.filter((s) => String(s.trial_id) === String(siteProtocolFilter))

  async function handleCleanSlateReset() {
    setCleanSlateBusy(true)
    setCleanSlateResult(null)
    try {
      const res = await resetTrialData()
      setCleanSlateResult(res)
      loadData()
    } catch (err) {
      alert(`Clean slate reset failed: ${err.message}`)
    } finally {
      setCleanSlateBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Official Government Page Banner */}
      <div className="border border-slate-300 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Government of India &middot; Ministry of Ayush &middot; AIIA CTMS Unit
            </div>
            <h2 className="text-lg font-bold text-slate-900 mt-1">
              Clinical Infrastructure &amp; Administrative Actions
            </h2>
            <p className="text-xs text-slate-600 mt-0.5">
              Master control center for Clinical Trial Protocols, Participating Hospital Centers, and Production Data States.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setShowTrialModal(true)}
              className="border border-slate-800 bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-black transition"
            >
              + Define Trial Protocol
            </button>
            <button
              onClick={() => setShowSiteModal(true)}
              className="border border-slate-400 bg-slate-100 px-4 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-200 transition"
            >
              + Register Hospital Site
            </button>
            <button
              onClick={() => setShowResetConfirm(true)}
              className="border border-red-400 bg-red-50 px-4 py-2 text-xs font-semibold text-red-800 hover:bg-red-100 transition"
            >
              Reset Test Data (Clean Slate)
            </button>
          </div>
        </div>
      </div>

      {/* Section 1: Participating Hospital Sites Registry */}
      <div className="border border-slate-300 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
              1. Participating Hospital &amp; Research Centers Registry ({displaySites.length} {siteProtocolFilter === 'all' ? 'Distinct Centers' : 'Active Sites'})
            </h3>
            <p className="text-[11px] text-slate-500">
              Official hospital sites authorized for GCP-ASU clinical trial participant recruitment and monitoring.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            {trials.length > 0 && (
              <div className="flex items-center gap-1.5 text-xs">
                <label htmlFor="protocol-site-filter" className="font-semibold text-slate-600">
                  Protocol Scope:
                </label>
                <select
                  id="protocol-site-filter"
                  value={siteProtocolFilter}
                  onChange={(e) => setSiteProtocolFilter(e.target.value)}
                  className="border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-800 shadow-sm focus:border-slate-800 focus:outline-none"
                >
                  <option value="all">
                    All Distinct Research Centers ({distinctCenters.length})
                  </option>
                  {trials.map((t) => (
                    <option key={t.id} value={t.id}>
                      Protocol: {t.protocol_number} &mdash; {t.title?.slice(0, 32)}{t.title?.length > 32 ? '...' : ''}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <button
              onClick={() => setShowSiteModal(true)}
              className="border border-slate-400 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-800 hover:bg-slate-100"
            >
              + Add New Site
            </button>
          </div>
        </div>

        <div className="mt-4 border border-slate-300 overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-slate-100 border-b border-slate-300 text-[11px] font-bold uppercase tracking-wider text-slate-700">
              <tr>
                <th className="border-r border-slate-300 px-3.5 py-2.5">Site Code</th>
                <th className="border-r border-slate-300 px-3.5 py-2.5">Hospital / Institute Name</th>
                <th className="border-r border-slate-300 px-3.5 py-2.5">City &amp; State</th>
                <th className="border-r border-slate-300 px-3.5 py-2.5">Principal Investigator</th>
                <th className="border-r border-slate-300 px-3.5 py-2.5">Official Contact</th>
                <th className="border-r border-slate-300 px-3.5 py-2.5">Enrolment Quota</th>
                <th className="px-3.5 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                    Loading participating hospital sites...
                  </td>
                </tr>
              ) : displaySites.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                    No participating hospital sites found for the selected scope.
                  </td>
                </tr>
              ) : (
                displaySites.map((s) => {
                  const isAllScope = siteProtocolFilter === 'all'
                  const pIds = s.protocol_ids || (s.trial_id ? [s.trial_id] : [])
                  const quota = isAllScope ? (s.total_target_enrollment ?? s.target_enrollment) : s.target_enrollment

                  return (
                    <tr key={isAllScope ? s.site_code : s.id} className="hover:bg-slate-50">
                      <td className="border-r border-slate-200 px-3.5 py-2.5 font-mono font-bold text-slate-900">
                        {s.site_code}
                      </td>
                      <td className="border-r border-slate-200 px-3.5 py-2.5 font-semibold text-slate-900">
                        <div>{s.name}</div>
                        {isAllScope && pIds.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {pIds.map((pId) => {
                              const tr = trialMap[pId]
                              return (
                                <span
                                  key={pId}
                                  title={tr ? tr.title : undefined}
                                  className="inline-block border border-slate-200 bg-slate-100 px-1.5 py-0.5 text-[9px] font-mono font-semibold text-slate-600"
                                >
                                  {tr ? tr.protocol_number : `Protocol #${pId}`}
                                </span>
                              )
                            })}
                          </div>
                        )}
                        {!isAllScope && trialMap[s.trial_id] && (
                          <div className="mt-0.5 text-[10px] font-mono text-slate-500">
                            Protocol: {trialMap[s.trial_id].protocol_number}
                          </div>
                        )}
                      </td>
                      <td className="border-r border-slate-200 px-3.5 py-2.5 text-slate-700">
                        {s.city}, {s.state}
                      </td>
                      <td className="border-r border-slate-200 px-3.5 py-2.5 text-slate-800">
                        <div className="font-semibold">{s.pi_name}</div>
                        {s.pi_email && <div className="font-mono text-[11px] text-slate-500">{s.pi_email}</div>}
                      </td>
                      <td className="border-r border-slate-200 px-3.5 py-2.5 font-mono text-[11px] text-slate-600">
                        {s.contact_phone || '—'}
                      </td>
                      <td className="border-r border-slate-200 px-3.5 py-2.5 font-bold text-slate-900">
                        <div>{quota} subjects</div>
                        {isAllScope && pIds.length > 1 && (
                          <div className="text-[10px] font-normal text-slate-500 mt-0.5">
                            Cumulative ({pIds.length} protocols)
                          </div>
                        )}
                      </td>
                      <td className="px-3.5 py-2.5">
                        <span className={`border px-2 py-0.5 text-[10px] font-bold uppercase ${
                          s.status === 'recruiting'
                            ? 'border-emerald-600 bg-emerald-50 text-emerald-800'
                            : 'border-slate-400 bg-slate-100 text-slate-800'
                        }`}>
                          {s.status}
                        </span>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Section 2: Clinical Trial Protocols Master Registry */}
      <div className="border border-slate-300 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
              2. Clinical Trial Protocols Master Registry ({trials.length} Protocols)
            </h3>
            <p className="text-[11px] text-slate-500">
              Statutory clinical trial protocols registered under CDSCO New Drugs &amp; Clinical Trials Rules 2019.
            </p>
          </div>
          <button
            onClick={() => setShowTrialModal(true)}
            className="border border-slate-400 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-800 hover:bg-slate-100"
          >
            + Register Protocol
          </button>
        </div>

        <div className="mt-4 border border-slate-300 overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-slate-100 border-b border-slate-300 text-[11px] font-bold uppercase tracking-wider text-slate-700">
              <tr>
                <th className="border-r border-slate-300 px-3.5 py-2.5">Protocol ID</th>
                <th className="border-r border-slate-300 px-3.5 py-2.5">Scientific Title &amp; Formulation</th>
                <th className="border-r border-slate-300 px-3.5 py-2.5">Trial Phase</th>
                <th className="border-r border-slate-300 px-3.5 py-2.5">Indication</th>
                <th className="border-r border-slate-300 px-3.5 py-2.5">CTRI Number</th>
                <th className="border-r border-slate-300 px-3.5 py-2.5">Ethics Approval</th>
                <th className="px-3.5 py-2.5">Lifecycle Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                    Loading clinical trial protocols...
                  </td>
                </tr>
              ) : trials.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                    No clinical trial protocols found.
                  </td>
                </tr>
              ) : (
                trials.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-50">
                    <td className="border-r border-slate-200 px-3.5 py-2.5 font-mono font-bold text-slate-900">
                      {t.protocol_number}
                    </td>
                    <td className="border-r border-slate-200 px-3.5 py-2.5">
                      <div className="font-bold text-slate-900">{t.title}</div>
                      <div className="text-[11px] text-slate-600 mt-0.5">
                        <strong>IP:</strong> {t.intervention}
                      </div>
                      {t.comparator && (
                        <div className="text-[10px] text-slate-500">
                          <strong>Control:</strong> {t.comparator}
                        </div>
                      )}
                    </td>
                    <td className="border-r border-slate-200 px-3.5 py-2.5 font-semibold uppercase text-slate-800">
                      {t.phase}
                    </td>
                    <td className="border-r border-slate-200 px-3.5 py-2.5 text-slate-700">
                      <div>{t.indication}</div>
                      {t.indication_ayurveda && (
                        <div className="text-[10px] text-slate-500 italic">
                          Ayush: {t.indication_ayurveda}
                        </div>
                      )}
                    </td>
                    <td className="border-r border-slate-200 px-3.5 py-2.5 font-mono text-[11px]">
                      {t.ctri_number ? (
                        <span className="font-bold text-slate-900">{t.ctri_number}</span>
                      ) : (
                        <span className="text-slate-400 italic">Pending Reg.</span>
                      )}
                    </td>
                    <td className="border-r border-slate-200 px-3.5 py-2.5 text-[11px]">
                      {t.ethics_approval_number ? (
                        <div>
                          <span className="font-mono font-semibold text-emerald-800">
                            {t.ethics_approval_number}
                          </span>
                          <div className="text-[10px] text-slate-500">
                            Status: {t.ethics_approval_status || 'Approved'}
                          </div>
                        </div>
                      ) : (
                        <span className="text-amber-800 italic">Review Pending</span>
                      )}
                    </td>
                    <td className="px-3.5 py-2.5">
                      <span className="border border-slate-400 bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase text-slate-800">
                        {t.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Section 3: Statutory Production Data Control */}
      <div className="border border-slate-300 bg-white p-5 shadow-sm">
        <div className="border-b border-slate-200 pb-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
            3. Production Data Reset &amp; Clean Slate Control
          </h3>
          <p className="text-[11px] text-slate-500">
            Statutory tool to wipe synthetic test subjects and initiate 100% real subject screening under 21 CFR Part 11.
          </p>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-4 border border-slate-200 bg-slate-50 p-4">
          <div className="max-w-2xl text-xs text-slate-700">
            <strong>Clean Slate Mode:</strong> Permanently purges synthetic participant records, simulated visits, and test adverse events while safely preserving trial definitions, registered hospital sites, personnel user accounts, and immutable audit logs.
          </div>
          <button
            onClick={() => setShowResetConfirm(true)}
            className="border border-red-700 bg-red-700 px-4 py-2 text-xs font-semibold text-white hover:bg-red-800"
          >
            Execute Clean Slate Reset
          </button>
        </div>
      </div>

      {/* Create Trial Modal */}
      {showTrialModal && (
        <CreateTrialModal
          onClose={() => setShowTrialModal(false)}
          onSuccess={() => loadData()}
        />
      )}

      {/* Create Site Modal */}
      {showSiteModal && (
        <CreateSiteModal
          onClose={() => setShowSiteModal(false)}
          onSuccess={() => loadData()}
        />
      )}

      {/* Clean Slate Confirmation Modal */}
      {showResetConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4">
          <div className="w-full max-w-lg border border-slate-400 bg-white p-6 shadow-xl">
            <h3 className="text-base font-bold text-slate-900 border-b border-slate-200 pb-2">
              Confirm Production Clean Slate Reset
            </h3>
            <p className="text-xs text-slate-600 mt-2">
              This administrative action clears all synthetic participant records and simulated clinical visits to prepare the CTMS portal for 100% real subject intake.
            </p>

            {cleanSlateResult ? (
              <div className="mt-4 border border-emerald-600 bg-emerald-50 p-4 text-xs text-emerald-900 space-y-2">
                <p className="font-bold">RESET COMPLETED SUCCESSFULLY</p>
                <p>&bull; Cleared {cleanSlateResult.cleared_subjects} synthetic participant dossiers.</p>
                <p>&bull; Cleared {cleanSlateResult.cleared_visits} study visit records.</p>
                <p>&bull; Cleared {cleanSlateResult.cleared_clinical_logs || 0} clinical progress logs.</p>
                <p>&bull; Cleared {cleanSlateResult.cleared_adverse_events} adverse events.</p>
                <p>&bull; Cleared {cleanSlateResult.cleared_econsents || 0} electronic consents.</p>
                <p>&bull; Cleared {cleanSlateResult.cleared_patient_accounts || 0} synthetic patient logins.</p>
                <p>&bull; Preserved {cleanSlateResult.preserved_sites} registered hospital sites and {cleanSlateResult.preserved_staff_users} authorized staff accounts.</p>
                <div className="pt-2">
                  <button
                    onClick={() => {
                      setShowResetConfirm(false)
                      setCleanSlateResult(null)
                    }}
                    className="border border-emerald-700 bg-emerald-700 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-800"
                  >
                    Close
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-4 space-y-3 text-xs">
                <div className="border border-amber-300 bg-amber-50 p-3 text-amber-900 text-[11px]">
                  <strong>Notice:</strong> All synthetic participant records, visits, clinical logs, adverse events, and e-consents across all trials and sites will be permanently purged. Core trial protocols, registered hospital sites, staff accounts, and statutory 21 CFR Part 11 audit logs will be preserved.
                </div>
                <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-200">
                  <button
                    type="button"
                    onClick={() => setShowResetConfirm(false)}
                    className="border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={cleanSlateBusy}
                    onClick={handleCleanSlateReset}
                    className="border border-red-700 bg-red-700 px-4 py-2 text-xs font-semibold text-white hover:bg-red-800 disabled:opacity-50"
                  >
                    {cleanSlateBusy ? 'Executing Reset...' : 'Execute Clean Slate Reset'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
