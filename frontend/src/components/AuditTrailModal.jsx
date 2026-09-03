import { useEffect, useState } from 'react'
import { fetchAuditLogs } from '../api'

export default function AuditTrailModal({ scopeSiteId, scopeTrialId, onClose }) {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionFilter, setActionFilter] = useState('')

  useEffect(() => {
    setLoading(true)
    const params = { limit: 50 }
    if (scopeTrialId) params.trial_id = scopeTrialId
    if (actionFilter) params.action = actionFilter

    fetchAuditLogs(params)
      .then((data) => {
        setLogs(data.items || [])
      })
      .catch((err) => {
        setError(err?.message || 'Failed to fetch audit records')
      })
      .finally(() => setLoading(false))
  }, [scopeSiteId, scopeTrialId, actionFilter])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-5xl flex-col rounded-2xl bg-white shadow-2xl overflow-hidden border border-slate-200">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-white text-lg shadow-sm">
              📜
            </span>
            <div>
              <h2 className="text-base font-semibold text-slate-900">
                Immutable Clinical Audit Trail
              </h2>
              <p className="text-xs text-slate-500">
                ALCOA+ & 21 CFR Part 11 Inspection-Readiness Record {scopeSiteId ? `(Scoped to Site ${scopeSiteId})` : '(Enterprise Portfolio)'}
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

        {/* Filters */}
        <div className="flex items-center justify-between border-b border-slate-100 bg-white px-6 py-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="font-medium text-slate-700">Filter Action:</span>
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs text-slate-800"
            >
              <option value="">All Actions</option>
              <option value="create">Create</option>
              <option value="update">Update</option>
              <option value="delete">Delete</option>
            </select>
          </div>
          <div className="text-[11px] text-slate-500 font-mono">
            Showing latest {logs.length} immutable records &bull; SHA-256 Hash Chained
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="p-12 text-center text-xs text-slate-500">
              Retrieving cryptographic audit trail logs...
            </div>
          ) : error ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800">
              {error}
            </div>
          ) : logs.length === 0 ? (
            <div className="p-12 text-center text-xs text-slate-500">
              No audit records found matching this scope.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-[11px] font-semibold text-slate-600 uppercase tracking-wider">
                    <th className="px-4 py-2.5">Timestamp (UTC / IST)</th>
                    <th className="px-4 py-2.5">User</th>
                    <th className="px-4 py-2.5">Action</th>
                    <th className="px-4 py-2.5">Entity</th>
                    <th className="px-4 py-2.5">Label / Identifier</th>
                    <th className="px-4 py-2.5">Regulatory Justification</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {logs.map((log) => {
                    const utcDate = new Date(log.timestamp)
                    return (
                      <tr key={log.id} className="hover:bg-slate-50/70 transition-colors">
                        <td className="px-4 py-3 font-mono text-[11px] text-slate-600 whitespace-nowrap">
                          {utcDate.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST
                          <div className="text-[10px] text-slate-400">
                            {utcDate.toISOString()}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="font-medium text-slate-900">{log.user_email}</div>
                          <div className="text-[10px] text-slate-500 uppercase">{log.user_role}</div>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className={`inline-flex items-center rounded px-2 py-0.5 text-[10px] font-semibold ${
                            log.action === 'create'
                              ? 'bg-emerald-100 text-emerald-800'
                              : log.action === 'update'
                              ? 'bg-blue-100 text-blue-800'
                              : 'bg-rose-100 text-rose-800'
                          }`}>
                            {log.action?.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-mono text-slate-700">
                          {log.entity_type}
                        </td>
                        <td className="px-4 py-3 font-mono text-slate-900 font-medium">
                          {log.entity_label || log.entity_id}
                        </td>
                        <td className="px-4 py-3 text-slate-600 max-w-xs truncate" title={log.reason}>
                          {log.reason || 'System recorded event'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-slate-200 bg-slate-50 px-6 py-3 flex items-center justify-between text-xs">
          <span className="text-slate-500">
            🔒 Read-only Sponsor Inspection Mode &bull; Append-only audit trail cannot be modified or purged.
          </span>
          <button
            onClick={onClose}
            className="rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow hover:bg-slate-800 transition"
          >
            Close Audit View
          </button>
        </div>
      </div>
    </div>
  )
}
