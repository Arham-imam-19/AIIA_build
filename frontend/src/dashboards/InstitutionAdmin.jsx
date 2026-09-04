// Institution Administrator: manages hospital site operations, coordinates researchers,
// monitors local recruitment & safety, and resolves data queries.

import { useState } from 'react'
import { api, fetchUsers, updateUser, fetchAuditLogs } from '../api'
import { useEffect } from 'react'
import DashboardLayout from './layout'

function ProvisionModal({ onClose, onSuccess }) {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('principal_investigator')
  const [password, setPassword] = useState('Welcome@2026')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api('/api/users', {
        method: 'POST',
        body: {
          full_name: fullName,
          email,
          role,
          password,
        },
      })
      onSuccess?.()
      onClose()
    } catch (err) {
      setError(err.detail || err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <h3 className="text-base font-semibold text-slate-900">
          Provision Local Staff
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          Register a new Principal Investigator or Clinical Research Coordinator for your site.
        </p>

        {error && (
          <div className="mt-3 rounded-lg bg-red-50 p-3 text-xs text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-700">Full Name</label>
            <input required value={fullName} onChange={(e) => setFullName(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 p-2.5 text-sm text-slate-800 outline-none focus:border-aiia-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700">Email Address</label>
            <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 p-2.5 text-sm text-slate-800 outline-none focus:border-aiia-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700">Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2 text-sm text-slate-800 outline-none focus:border-aiia-500">
              <option value="principal_investigator">Principal Investigator</option>
              <option value="coordinator">Clinical Research Coordinator</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700">Initial Password</label>
            <input required type="text" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 p-2.5 text-sm text-slate-800 outline-none focus:border-aiia-500" />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50">Cancel</button>
            <button type="submit" disabled={busy} className="rounded-lg bg-aiia-600 px-4 py-2 text-xs font-medium text-white hover:bg-aiia-700 disabled:opacity-50">{busy ? 'Provisioning...' : 'Provision User'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function InstitutionAdmin(props) {
  const [showProvision, setShowProvision] = useState(false)
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(false)
  const [auditLogs, setAuditLogs] = useState([])

  const ROLE_DISPLAY_NAMES = {
    principal_investigator: 'Principal Investigator',
    coordinator: 'Clinical Research Coordinator',
    monitor: 'Monitor'
  }

  function loadUsers() {
    setLoading(true)
    fetchUsers({ limit: 100 })
      .then((res) => {
        setUsers(res.items || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }

  useEffect(() => {
    loadUsers()
    fetchAuditLogs({ limit: 100 }).then(res => setAuditLogs(res.items || [])).catch(() => {})
  }, [])

  async function handleToggleActive(user) {
    try {
      await updateUser(user.id, { is_active: !user.is_active })
      loadUsers()
      props.onRefresh?.()
    } catch (err) {
      alert(`Failed to update user status: ${err.message}`)
    }
  }


  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between rounded-lg border border-teal-100 bg-teal-50/70 px-4 py-2.5 text-xs text-teal-900">
        <span className="flex items-center gap-2 font-medium">
          <span className="flex h-2 w-2 rounded-full bg-teal-600"></span>
          🏥 Site Healthcare Provider Scope: Local Operations
        </span>
        <span className="text-teal-700 hidden sm:inline">
          Access is limited to participants enrolled at your hospital site.
        </span>
      </div>

      <DashboardLayout
        {...props}
        dashboard={{
          ...props.dashboard,
          subtitle: 'Site governance, researcher coordination, and recruitment KPIs.',
          blocks: (props.dashboard?.blocks || []).filter(b => !['staff', 'status_breakdown'].includes(b.key))
        }}
        wide={['open_queries']}
        note="Institution Scope: Manage hospital research personnel, track patient enrollment milestones, and resolve CRA data queries."
      />

            <div className="mt-4 border border-slate-300 bg-white p-5 shadow-sm">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 mb-4">
          Local Authorized Personnel
        </h4>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse border border-slate-300">
            <thead className="bg-slate-100 border-b border-slate-300 text-[11px] font-bold uppercase tracking-wider text-slate-700">
              <tr>
                <th className="border-r border-slate-300 px-3.5 py-2.5">Name &amp; Email</th>
                <th className="border-r border-slate-300 px-3.5 py-2.5">Role</th>
                <th className="border-slate-300 px-3.5 py-2.5">Account Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {loading ? (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-slate-500">
                    Loading local directory...
                  </td>
                </tr>
              ) : (
                users.filter(u => ['principal_investigator', 'coordinator', 'monitor'].includes(u.role)).map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50">
                    <td className="border-r border-slate-200 px-3.5 py-2.5">
                      <div className="font-bold text-slate-900">{u.full_name}</div>
                      <div className="font-mono text-[11px] text-slate-600">{u.email}</div>
                    </td>
                    <td className="border-r border-slate-200 px-3.5 py-2.5 font-semibold text-slate-800">
                      {ROLE_DISPLAY_NAMES[u.role] || u.role}
                    </td>
                    <td className="border-slate-200 px-3.5 py-2.5">
                      <button
                        onClick={() => handleToggleActive(u)}
                        className={`border px-2.5 py-0.5 text-[10px] font-bold uppercase ${
                          u.is_active
                            ? 'border-emerald-600 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
                            : 'border-red-600 bg-red-50 text-red-800 hover:bg-red-100'
                        }`}
                      >
                        {u.is_active ? 'Active' : 'Suspended'}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-sm font-semibold text-slate-800">
              Staff Provisioning
            </h4>
            <p className="text-xs text-slate-500">
              Add a new Principal Investigator or Clinical Research Coordinator to this site.
            </p>
          </div>
          <button
            onClick={() => setShowProvision(true)}
            className="rounded-lg bg-aiia-600 px-3.5 py-2 text-xs font-medium text-white shadow-sm hover:bg-aiia-700"
          >
            + Provision Local Staff
          </button>
        </div>
      </div>

      {showProvision && (
        <ProvisionModal
          onClose={() => setShowProvision(false)}
          onSuccess={props.onRefresh}
        />
      )}

      <div className="mt-4 border border-slate-300 bg-white p-5 shadow-sm">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 mb-4">
          Local System Access Audit (21 CFR Part 11)
        </h4>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse border border-slate-300">
            <thead className="bg-slate-100 border-b border-slate-300 text-[11px] font-bold uppercase tracking-wider text-slate-700">
              <tr>
                <th className="border-r border-slate-300 px-3.5 py-2.5">When</th>
                <th className="border-r border-slate-300 px-3.5 py-2.5">Who</th>
                <th className="border-r border-slate-300 px-3.5 py-2.5">Role</th>
                <th className="border-slate-300 px-3.5 py-2.5">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {auditLogs.filter(log => ['principal_investigator', 'coordinator'].includes(log.user_role)).length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                    No local access audit records found.
                  </td>
                </tr>
              ) : (
                auditLogs
                  .filter(log => ['principal_investigator', 'coordinator'].includes(log.user_role))
                  .slice(0, 20)
                  .map((log, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="border-r border-slate-200 px-3.5 py-2.5 font-mono text-[10px]">
                      {log.timestamp_ist ? new Date(log.timestamp_ist).toLocaleString() : new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="border-r border-slate-200 px-3.5 py-2.5">{log.user_email}</td>
                    <td className="border-r border-slate-200 px-3.5 py-2.5">{(log.user_role || '').replace('_', ' ')}</td>
                    <td className="border-slate-200 px-3.5 py-2.5 font-semibold text-slate-700">{log.action}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
