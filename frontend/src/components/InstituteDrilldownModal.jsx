import { useEffect, useState } from 'react'
import { fetchInstituteDrilldown } from '../api'

export default function InstituteDrilldownModal({ siteId, onClose, onOpenAudit }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!siteId) return
    setLoading(true)
    fetchInstituteDrilldown(siteId)
      .then((res) => {
        setData(res)
      })
      .catch((err) => {
        setError(err?.message || 'Failed to load institute drilldown')
      })
      .finally(() => setLoading(false))
  }, [siteId])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-5xl flex-col rounded-2xl bg-white shadow-2xl overflow-hidden border border-slate-200">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-700 text-white text-lg shadow-sm">
              🏥
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-slate-900">
                  {data?.name || 'Participating Medical Institute'}
                </h2>
                {data && (
                  <span className="rounded bg-slate-200 px-2 py-0.5 text-xs font-mono font-medium text-slate-700">
                    Site {data.site_code}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500">
                {data ? `${data.city}, ${data.state} &bull; Status: ${data.status?.toUpperCase()}` : 'Institute Clinical Governance Breakdown'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200 hover:text-slate-700 transition"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="p-12 text-center text-xs text-slate-500">
              Loading institute metrics and study breakdown...
            </div>
          ) : error ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800">
              {error}
            </div>
          ) : (
            <>
              {/* Top Banner with Site Overview & Audit Action */}
              <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-200 bg-slate-50/50 p-4">
                <div className="flex items-center gap-6 text-xs">
                  <div>
                    <span className="text-slate-500 block text-[11px]">Site Status:</span>
                    <span className="font-semibold text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded text-[11px]">
                      {data.status?.toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">Activation Date:</span>
                    <span className="font-medium text-slate-900 font-mono">
                      {data.activation_date || 'Standard Activation'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">Studies Operating:</span>
                    <span className="font-medium text-slate-900">
                      {data.studies?.length || 0} Trial Protocol
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => onOpenAudit?.(data.site_id)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition"
                >
                  <span>📜</span>
                  <span>View Site Audit Trail</span>
                </button>
              </div>

              {/* Department / Study Breakdown Table */}
              <div>
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-900">
                    Department & Protocol Operations Breakdown
                  </h3>
                  <span className="text-[11px] text-slate-500">
                    Live SQL aggregates scoped to Institute [{data.site_code}]
                  </span>
                </div>

                <div className="overflow-x-auto rounded-xl border border-slate-200">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-slate-200 bg-slate-50 text-[11px] font-semibold text-slate-600 uppercase tracking-wider">
                        <th className="px-4 py-2.5">Department / Study Name</th>
                        <th className="px-4 py-2.5">Principal Investigator</th>
                        <th className="px-4 py-2.5 text-right">Screened</th>
                        <th className="px-4 py-2.5 text-right">Enrolled</th>
                        <th className="px-4 py-2.5 text-right">Target</th>
                        <th className="px-4 py-2.5 text-right">% of Target</th>
                        <th className="px-4 py-2.5 text-center">Status</th>
                        <th className="px-4 py-2.5 text-right">Open AEs</th>
                        <th className="px-4 py-2.5 text-right">Deviations</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {data.studies?.map((s) => (
                        <tr key={s.study_id} className="hover:bg-slate-50/70 transition-colors">
                          <td className="px-4 py-3 font-medium text-slate-900">
                            <div>{s.department_study_name}</div>
                            <div className="text-[11px] font-mono text-slate-500">
                              Protocol: {s.protocol_number}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-slate-700">
                            {s.pi_name}
                          </td>
                          <td className="px-4 py-3 font-mono text-right text-slate-700">
                            {s.screened}
                          </td>
                          <td className="px-4 py-3 font-mono text-right font-semibold text-slate-900">
                            {s.enrolled}
                          </td>
                          <td className="px-4 py-3 font-mono text-right text-slate-600">
                            {s.target}
                          </td>
                          <td className="px-4 py-3 font-mono text-right">
                            <span className={`font-semibold ${
                              s.percent_of_target >= 80 ? 'text-emerald-700' : 'text-amber-700'
                            }`}>
                              {s.percent_of_target}%
                            </span>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span className="inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-800">
                              {s.status?.toUpperCase()}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono text-right">
                            <span className={s.open_aes > 0 ? 'text-amber-700 font-semibold' : 'text-slate-500'}>
                              {s.open_aes}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono text-right">
                            <span className={s.deviations > 10 ? 'text-rose-700 font-semibold' : 'text-slate-700'}>
                              {s.deviations} ({s.deviation_rate}%)
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-slate-200 bg-slate-50 px-6 py-3 flex items-center justify-between text-xs">
          <span className="text-slate-500">
            🔒 Sponsor Oversight Mode &bull; Strictly Read-Only View
          </span>
          <button
            onClick={onClose}
            className="rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow hover:bg-slate-800 transition"
          >
            Close Drill-Down
          </button>
        </div>
      </div>
    </div>
  )
}
