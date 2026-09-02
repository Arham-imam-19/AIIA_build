import { useEffect, useState } from 'react'
import { fetchSiteResearchOverview } from '../api'

export default function SiteResearchModal({ siteId, siteName, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!siteId) return
    setLoading(true)
    setError(null)
    fetchSiteResearchOverview(siteId)
      .then(setData)
      .catch((err) => {
        setError(err?.detail || err?.message || 'Failed to load site research overview')
      })
      .finally(() => setLoading(false))
  }, [siteId])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-lg bg-white shadow-2xl border border-slate-300">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-200 bg-slate-100 px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded bg-indigo-900 text-sm font-bold text-white shadow-sm font-mono">
              {data?.site_code || 'SITE'}
            </span>
            <div>
              <h2 className="text-base font-bold text-slate-900 leading-tight">
                {data?.name || siteName || 'Institutional Research Profile'}
              </h2>
              <p className="text-xs text-slate-600">
                {data ? `${data.city}, ${data.state}, ${data.country}` : 'Loading location...'} &bull; Primary PI: {data?.pi_name || 'Assigned Investigator'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-200 transition-colors"
          >
            ✕ Close
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center p-12 text-slate-500">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-300 border-t-indigo-900 mb-3"></div>
              <p className="text-sm font-medium">Loading institutional research overview &amp; site capacity metrics...</p>
            </div>
          ) : error ? (
            <div className="rounded border border-red-200 bg-red-50 p-4 text-xs text-red-800">
              <strong>Error:</strong> {error}
            </div>
          ) : (
            <>
              {/* Site Capacity & Operational Health KPIs */}
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
                  Site Clinical Capacity &amp; Operational Health
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-xs">
                  <div className="border border-slate-200 bg-slate-50 p-3 rounded">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">Active Protocols</span>
                    <span className="text-xl font-bold text-slate-900 mt-0.5 block">{data.total_trials}</span>
                  </div>
                  <div className="border border-slate-200 bg-slate-50 p-3 rounded">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">Enrolled Patients</span>
                    <span className="text-xl font-bold text-indigo-700 mt-0.5 block">{data.total_enrolled_subjects}</span>
                  </div>
                  <div className="border border-slate-200 bg-slate-50 p-3 rounded">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">Screened Total</span>
                    <span className="text-xl font-bold text-slate-700 mt-0.5 block">{data.total_screened_subjects}</span>
                  </div>
                  <div className="border border-amber-200 bg-amber-50 p-3 rounded">
                    <span className="text-[10px] uppercase font-bold text-amber-700 block">Open Deviations</span>
                    <span className="text-xl font-bold text-amber-900 mt-0.5 block">{data.total_open_deviations}</span>
                  </div>
                  <div className={`border p-3 rounded ${data.total_active_saes > 0 ? 'border-red-200 bg-red-50' : 'border-slate-200 bg-slate-50'}`}>
                    <span className={`text-[10px] uppercase font-bold block ${data.total_active_saes > 0 ? 'text-red-700' : 'text-slate-400'}`}>
                      Active SAE Reports
                    </span>
                    <span className={`text-xl font-bold mt-0.5 block ${data.total_active_saes > 0 ? 'text-red-700' : 'text-slate-700'}`}>
                      {data.total_active_saes}
                    </span>
                  </div>
                  <div className="border border-slate-200 bg-slate-50 p-3 rounded">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">Registered Staff</span>
                    <span className="text-xl font-bold text-slate-900 mt-0.5 block">{data.total_staff_count}</span>
                  </div>
                </div>
              </div>

              {/* Visual Multi-centric Hierarchy */}
              <div className="border border-slate-200 bg-slate-50/70 p-4 rounded text-xs">
                <div className="font-bold text-slate-800 mb-2 flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-emerald-600"></span>
                  Multi-Centric Trial Hierarchy &amp; Jurisdiction
                </div>
                <div className="flex flex-wrap items-center gap-2 text-slate-600 font-mono text-[11px]">
                  <span className="px-2.5 py-1 bg-white border border-slate-300 rounded font-semibold text-slate-800">
                    🏥 Hospital Site: {data.name}
                  </span>
                  <span>&rarr;</span>
                  <span className="px-2.5 py-1 bg-white border border-slate-300 rounded font-semibold text-slate-800">
                    👨‍⚕️ Principal PI: {data.pi_name}
                  </span>
                  <span>&rarr;</span>
                  <span className="px-2.5 py-1 bg-white border border-slate-300 rounded font-semibold text-indigo-700">
                    🔬 {data.total_trials} Active Study Protocol{data.total_trials === 1 ? '' : 's'}
                  </span>
                  <span>&rarr;</span>
                  <span className="px-2.5 py-1 bg-white border border-slate-300 rounded font-semibold text-emerald-700">
                    👥 {data.total_enrolled_subjects} Enrolled Participants
                  </span>
                </div>
              </div>

              {/* Research Protocols Table */}
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
                  Associated Clinical Research Protocols ({data.trials.length})
                </h3>
                {data.trials.length === 0 ? (
                  <div className="rounded border border-slate-200 bg-slate-50 p-6 text-center text-xs text-slate-500">
                    No active clinical research protocols currently associated with this site.
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded border border-slate-200 bg-white shadow-sm">
                    <table className="w-full text-left text-xs text-slate-700">
                      <thead className="border-b border-slate-200 bg-slate-100 text-[11px] uppercase font-bold text-slate-600">
                        <tr>
                          <th className="px-4 py-3">Protocol Number</th>
                          <th className="px-4 py-3">Study Title &amp; Indication</th>
                          <th className="px-4 py-3">Phase / Status</th>
                          <th className="px-4 py-3">Site PI</th>
                          <th className="px-4 py-3">Enrolled / Target</th>
                          <th className="px-4 py-3">Ethics Clearance</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 font-sans">
                        {data.trials.map((t) => (
                          <tr key={t.trial_id} className="hover:bg-slate-50/80 transition-colors">
                            <td className="px-4 py-3 font-mono font-bold text-indigo-900 whitespace-nowrap">
                              {t.protocol_number}
                            </td>
                            <td className="px-4 py-3 max-w-xs">
                              <div className="font-semibold text-slate-900 line-clamp-1" title={t.title}>{t.title}</div>
                              <div className="text-[11px] text-slate-500">{t.indication}</div>
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap">
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-slate-200 text-slate-800 mr-1.5">
                                {t.phase.replace('_', ' ')}
                              </span>
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                                t.status === 'recruiting' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-700'
                              }`}>
                                {t.status}
                              </span>
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap">
                              <div className="font-medium text-slate-900">{t.site_pi_name || data.pi_name}</div>
                              <div className="text-[10px] text-slate-400">{t.site_pi_email || '-'}</div>
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap">
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-indigo-700">{t.site_enrolled_subjects}</span>
                                <span className="text-slate-400">/ {t.site_target_enrollment}</span>
                              </div>
                              <div className="w-20 bg-slate-100 h-1 rounded-full overflow-hidden mt-1">
                                <div
                                  className="bg-indigo-600 h-full"
                                  style={{
                                    width: `${Math.min(100, (t.site_enrolled_subjects / (t.site_target_enrollment || 1)) * 100)}%`,
                                  }}
                                ></div>
                              </div>
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap">
                              {t.ethics_approval_status === 'approved' ? (
                                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700">
                                  ✅ {t.ethics_approval_number || 'IEC Approved'}
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-700">
                                  ⏳ {t.ethics_approval_status || 'Pending IEC'}
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex justify-end border-t border-slate-200 bg-slate-50 px-6 py-3">
          <button
            onClick={onClose}
            className="rounded border border-slate-300 bg-white px-4 py-2 text-xs font-bold text-slate-700 hover:bg-slate-100 transition-colors"
          >
            Close Profile
          </button>
        </div>
      </div>
    </div>
  )
}
