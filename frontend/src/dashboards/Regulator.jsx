// Regulator (CDSCO / Ministry of Ayush): read-only across every site, plus the
// interactive ALCOA+ audit trail explorer under 21 CFR Part 11 and NDCT Rules 2019.

import { useEffect, useState } from 'react'
import { fetchAuditLogs } from '../api'
import DashboardLayout from './layout'
import DataExportCenter from '../components/DataExportCenter'

function AuditDiffViewer({ entry }) {
  let parsedOld = null
  let parsedNew = null
  try {
    if (entry.old_value) parsedOld = JSON.parse(entry.old_value)
  } catch {
    parsedOld = entry.old_value
  }
  try {
    if (entry.new_value) parsedNew = JSON.parse(entry.new_value)
  } catch {
    parsedNew = entry.new_value
  }

  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs font-mono">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-2 font-sans font-medium text-slate-700">
        <span className="flex items-center gap-1.5 text-slate-900 font-semibold">
          <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
          ALCOA+ Audit Record #{entry.id} &mdash; {entry.action.toUpperCase()} on {entry.entity_type}
        </span>
        <span className="text-slate-500">
          {entry.timestamp_ist || (entry.timestamp ? new Date(entry.timestamp).toISOString() : '-')} | IP: {entry.ip_address || '127.0.0.1'} | CERT-In 180-Day Retention
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="rounded border border-amber-200 bg-amber-50/50 p-2.5">
          <div className="mb-1 font-sans font-semibold text-amber-900">Previous State (Before)</div>
          <pre className="overflow-x-auto whitespace-pre-wrap text-[11px] text-slate-700">
            {parsedOld ? JSON.stringify(parsedOld, null, 2) : <span className="italic text-slate-400">None (Newly Created)</span>}
          </pre>
        </div>
        <div className="rounded border border-emerald-200 bg-emerald-50/50 p-2.5">
          <div className="mb-1 font-sans font-semibold text-emerald-900">Resulting State (After)</div>
          <pre className="overflow-x-auto whitespace-pre-wrap text-[11px] text-slate-700">
            {parsedNew ? JSON.stringify(parsedNew, null, 2) : <span className="italic text-slate-400">Unchanged / No Value</span>}
          </pre>
        </div>
      </div>

      {entry.reason && (
        <div className="mt-2.5 font-sans text-xs text-slate-600">
          <span className="font-semibold text-slate-800">Reason on Record:</span> {entry.reason}
        </div>
      )}
    </div>
  )
}

function InteractiveAuditExplorer() {
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [entityType, setEntityType] = useState('')
  const [action, setAction] = useState('')
  const [offset, setOffset] = useState(0)
  const [expandedId, setExpandedId] = useState(null)
  const limit = 10

  const entities = [
    { label: 'All Entities', value: '' },
    { label: 'Subjects', value: 'subjects' },
    { label: 'Trials', value: 'trials' },
    { label: 'Visits', value: 'visits' },
    { label: 'Adverse Events', value: 'adverse_events' },
    { label: 'e-Consent', value: 'econsents' },
    { label: 'Patient Requests', value: 'patient_requests' },
    { label: 'Users', value: 'users' },
  ]

  const actions = [
    { label: 'All Actions', value: '' },
    { label: 'Create', value: 'create' },
    { label: 'Update', value: 'update' },
    { label: 'Sign', value: 'sign' },
    { label: 'Approve', value: 'approve' },
    { label: 'Respond', value: 'respond' },
  ]

  async function loadLogs() {
    setLoading(true)
    setError('')
    try {
      const res = await fetchAuditLogs({
        search: search.trim() || undefined,
        entity_type: entityType || undefined,
        action: action || undefined,
        limit,
        offset,
      })
      setLogs(res.items || [])
      setTotal(res.total || 0)
    } catch (err) {
      setError(err?.message || 'Failed to load audit logs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadLogs()
  }, [search, entityType, action, offset])

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-slate-900">
              ALCOA+ Complete Audit Trail Explorer
            </h3>
            <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
              21 CFR Part 11
            </span>
          </div>
          <p className="mt-0.5 text-xs text-slate-500">
            Append-only, immutable regulatory ledger tracking all changes, before/after diffs, and attribution.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">
            Showing <strong className="font-semibold text-slate-700">{logs.length}</strong> of <strong className="font-semibold text-slate-700">{total}</strong> entries
          </span>
          <button
            onClick={() => loadLogs()}
            className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <label className="block text-xs font-medium text-slate-600">Search Records</label>
          <input
            type="text"
            placeholder="Search email, label, reason..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setOffset(0)
            }}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-1.5 text-xs placeholder-slate-400 focus:border-aiia-500 focus:outline-none focus:ring-1 focus:ring-aiia-500"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-600">Filter by Entity</label>
          <select
            value={entityType}
            onChange={(e) => {
              setEntityType(e.target.value)
              setOffset(0)
            }}
            className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:border-aiia-500 focus:outline-none"
          >
            {entities.map((ent) => (
              <option key={ent.value} value={ent.value}>{ent.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-600">Filter by Action</label>
          <select
            value={action}
            onChange={(e) => {
              setAction(e.target.value)
              setOffset(0)
            }}
            className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:border-aiia-500 focus:outline-none"
          >
            {actions.map((act) => (
              <option key={act.value} value={act.value}>{act.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
          <thead>
            <tr className="bg-slate-50 text-slate-600 font-medium">
              <th className="py-2.5 pl-3 pr-2">Timestamp (IST / UTC)</th>
              <th className="px-2 py-2.5">User</th>
              <th className="px-2 py-2.5">Role</th>
              <th className="px-2 py-2.5">Action</th>
              <th className="px-2 py-2.5">Entity / Record</th>
              <th className="px-2 py-2.5">Reason / Summary</th>
              <th className="py-2.5 pl-2 pr-3 text-right">Inspection</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-700">
            {loading && logs.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-slate-400">Loading audit records...</td>
              </tr>
            ) : logs.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-slate-400">No matching audit trail records found.</td>
              </tr>
            ) : (
              logs.map((entry) => {
                const isExpanded = expandedId === entry.id
                const utcStr = entry.timestamp ? new Date(entry.timestamp).toISOString().replace('T', ' ').slice(0, 19) + ' UTC' : '-'
                return (
                  <tr key={entry.id} className={`hover:bg-slate-50/75 transition-colors ${isExpanded ? 'bg-slate-50/60' : ''}`}>
                    <td className="py-2.5 pl-3 pr-2 whitespace-nowrap font-mono text-[11px] text-slate-700">
                      <div>{entry.timestamp_ist || utcStr}</div>
                      <div className="text-[10px] text-slate-400 font-sans">{utcStr}</div>
                    </td>
                    <td className="px-2 py-2.5 font-medium text-slate-900 truncate max-w-[140px]" title={entry.user_email || 'System'}>
                      {entry.user_email || 'System'}
                    </td>
                    <td className="px-2 py-2.5 capitalize text-slate-600 whitespace-nowrap">
                      {entry.user_role ? entry.user_role.replace('_', ' ') : '-'}
                    </td>
                    <td className="px-2 py-2.5 whitespace-nowrap">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${
                        entry.action === 'create' ? 'bg-blue-100 text-blue-800' :
                        entry.action === 'sign' ? 'bg-purple-100 text-purple-800' :
                        entry.action === 'approve' ? 'bg-emerald-100 text-emerald-800' :
                        entry.action === 'update' ? 'bg-amber-100 text-amber-800' :
                        'bg-slate-100 text-slate-800'
                      }`}>
                        {entry.action}
                      </span>
                    </td>
                    <td className="px-2 py-2.5 font-mono text-[11px] text-slate-800">
                      <span className="font-semibold text-slate-900">{entry.entity_type}</span> {entry.entity_label || `#${entry.entity_id || ''}`}
                    </td>
                    <td className="px-2 py-2.5 text-slate-600 truncate max-w-[200px]" title={entry.reason || '-'}>
                      {entry.reason || '-'}
                    </td>
                    <td className="py-2.5 pl-2 pr-3 text-right whitespace-nowrap">
                      <button
                        onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                        className={`rounded px-2 py-1 text-[11px] font-medium transition-colors ${
                          isExpanded
                            ? 'bg-aiia-600 text-white'
                            : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                        }`}
                      >
                        {isExpanded ? 'Hide Diff' : 'View Diff'}
                      </button>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Expanded Diff Viewer if an item is selected */}
      {expandedId && (
        <div className="mt-3">
          {(() => {
            const selected = logs.find((l) => l.id === expandedId)
            return selected ? <AuditDiffViewer entry={selected} /> : null
          })()}
        </div>
      )}

      {/* Pagination Footer */}
      <div className="mt-4 flex items-center justify-between border-t border-slate-200 pt-3 text-xs text-slate-500">
        <div>
          Page {Math.floor(offset / limit) + 1} of {Math.max(1, Math.ceil(total / limit))}
        </div>
        <div className="flex items-center gap-2">
          <button
            disabled={offset === 0 || loading}
            onClick={() => setOffset(Math.max(0, offset - limit))}
            className="rounded border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Previous
          </button>
          <button
            disabled={offset + limit >= total || loading}
            onClick={() => setOffset(offset + limit)}
            className="rounded border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </section>
  )
}

export default function Regulator(props) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between rounded-lg border border-indigo-100 bg-indigo-50/70 px-4 py-2.5 text-xs text-indigo-900">
        <span className="flex items-center gap-2 font-medium">
          <span className="flex h-2 w-2 rounded-full bg-indigo-600"></span>
          🔒 DPDP Act 2023 & NDCT Rules 2019: Data Minimized Oversight Mode Active
        </span>
        <span className="text-indigo-700 hidden sm:inline">
          Direct patient PII is redacted under statutory purpose limitation.
        </span>
      </div>

      <DataExportCenter />

      <DashboardLayout
        {...props}
        wide={['audit_tail', 'sae_reporting', 'ndct_gates']}
        note="The legal sequence under India's NDCT Rules 2019: IEC ethics approval, then regulatory permission, then CTRI registration before the first participant is enrolled."
      />

      <InteractiveAuditExplorer />
    </div>
  )
}
