import { useState, useEffect } from 'react'
import { api, fetchUsers, updateUser, fetchAuditLogs, fetchTrials, updateTrialStatus, activateTrial } from '../api'
import DashboardLayout from './layout'
import RegisterCtriModal from '../components/RegisterCtriModal'
import CreateTrialModal from '../components/CreateTrialModal'

const statusColors = {
  planning: 'bg-slate-100 text-slate-800 border-slate-300',
  pending_ethics: 'bg-amber-50 text-amber-800 border-amber-300',
  approved: 'bg-blue-50 text-blue-800 border-blue-300',
  recruiting: 'bg-emerald-50 text-emerald-800 border-emerald-300',
  active: 'bg-emerald-100 text-emerald-900 border-emerald-400',
  suspended: 'bg-red-50 text-red-800 border-red-300',
  completed: 'bg-slate-100 text-slate-800 border-slate-300',
  terminated: 'bg-red-100 text-red-900 border-red-400',
}

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
  const [showCreateTrialModal, setShowCreateTrialModal] = useState(false)
  const [showCtriModal, setShowCtriModal] = useState(false)
  const [users, setUsers] = useState([])
  const [trials, setTrials] = useState([])
  const [selectedTrialId, setSelectedTrialId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [auditLogs, setAuditLogs] = useState([])
  const [statusBusy, setStatusBusy] = useState(false)
  const [statusMsg, setStatusMsg] = useState(null)
  const [statusErr, setStatusErr] = useState(null)

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

  function loadTrials() {
    fetchTrials({ institution_only: true })
      .then((res) => {
        const items = res.items || []
        setTrials(items)
        if (items.length > 0 && !selectedTrialId) {
          setSelectedTrialId(items[0].id)
        }
      })
      .catch(() => {})
  }

  useEffect(() => {
    loadUsers()
    loadTrials()
    fetchAuditLogs({ limit: 100 }).then(res => setAuditLogs(res.items || [])).catch(() => {})
  }, [])

  const activeTrial = trials.find(t => t.id === selectedTrialId) || trials[0]

  async function handleQuickStatusChange(newStatus) {
    if (!activeTrial) return
    setStatusBusy(true)
    setStatusErr(null)
    setStatusMsg(null)
    try {
      await updateTrialStatus(activeTrial.id, {
        status: newStatus,
        reason: `Status transitioned to ${newStatus} by Institution Administrator.`
      })
      setStatusMsg(`Protocol ${activeTrial.protocol_number} status set to ${newStatus.toUpperCase()}`)
      loadTrials()
      props.onRefresh?.()
      setTimeout(() => setStatusMsg(null), 4000)
    } catch (err) {
      setStatusErr(err.detail || err.message || 'Failed to update protocol status')
      setTimeout(() => setStatusErr(null), 5000)
    } finally {
      setStatusBusy(false)
    }
  }

  async function handleQuickActivate() {
    if (!activeTrial) return
    setStatusBusy(true)
    setStatusErr(null)
    setStatusMsg(null)
    try {
      await activateTrial(activeTrial.id)
      setStatusMsg(`Protocol ${activeTrial.protocol_number} successfully activated for recruitment!`)
      loadTrials()
      props.onRefresh?.()
      setTimeout(() => setStatusMsg(null), 4000)
    } catch (err) {
      try {
        await updateTrialStatus(activeTrial.id, {
          status: 'recruiting',
          reason: 'Recruitment activated by Institution Administrator.'
        })
        setStatusMsg(`Protocol ${activeTrial.protocol_number} status set to RECRUITING.`)
        loadTrials()
        props.onRefresh?.()
        setTimeout(() => setStatusMsg(null), 4000)
      } catch (err2) {
        setStatusErr(err.detail || err.message || 'Failed to activate trial')
        setTimeout(() => setStatusErr(null), 5000)
      }
    } finally {
      setStatusBusy(false)
    }
  }

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
      {statusMsg && (
        <div className="rounded-lg border border-emerald-600 bg-emerald-50 p-3 text-xs font-bold text-emerald-900 shadow-sm flex items-center justify-between">
          <span>✅ {statusMsg}</span>
          <button onClick={() => setStatusMsg(null)} className="text-emerald-700 hover:text-emerald-950">✕</button>
        </div>
      )}

      {statusErr && (
        <div className="rounded-lg border border-red-600 bg-red-50 p-3 text-xs font-bold text-red-900 shadow-sm flex items-center justify-between">
          <span>⚠️ {statusErr}</span>
          <button onClick={() => setStatusErr(null)} className="text-red-700 hover:text-red-950">✕</button>
        </div>
      )}

      <div className="flex items-center justify-between rounded-lg border border-teal-100 bg-teal-50/70 px-4 py-2.5 text-xs text-teal-900">
        <span className="flex items-center gap-2 font-medium">
          <span className="flex h-2 w-2 rounded-full bg-teal-600"></span>
          🏥 Site Healthcare Provider Scope: Local Operations
        </span>
        <span className="text-teal-700 hidden sm:inline">
          Access is limited to participants enrolled at your hospital site.
        </span>
      </div>

      {/* Protocol Governance & Status Transition Controls for Institution Admin */}
      <div className="border border-slate-300 bg-white p-4 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
          <div className="w-full max-w-lg">
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-700 mb-1">
              Select Target Protocol (Institution Governance)
            </label>
            <select
              value={selectedTrialId || ''}
              onChange={e => setSelectedTrialId(Number(e.target.value))}
              className="w-full border border-slate-300 p-2 text-xs font-semibold text-slate-900 focus:border-slate-800 focus:outline-none"
            >
              {trials.map(p => (
                <option key={p.id} value={p.id}>
                  [{p.protocol_number}] {p.short_title || p.title} &middot; Status: {p.status?.toUpperCase()}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowCreateTrialModal(true)}
              className="border border-blue-900 bg-blue-900 px-3.5 py-2 text-xs font-bold text-white hover:bg-blue-800 transition shadow-sm"
            >
              + Create New Protocol
            </button>
            <button
              onClick={() => setShowProvision(true)}
              className="border border-slate-800 bg-slate-900 px-3.5 py-2 text-xs font-semibold text-white hover:bg-black transition"
            >
              + Provision Staff
            </button>
          </div>
        </div>

        {activeTrial && (
          <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 border border-slate-200 p-3 text-xs">
            <div className="flex flex-wrap items-center gap-3">
              <div>
                <span className="text-[10px] font-bold uppercase text-slate-500 block">Current Status</span>
                <span className={`inline-block border px-2.5 py-0.5 font-mono text-[11px] font-bold uppercase mt-0.5 ${statusColors[activeTrial.status] || 'bg-slate-100 text-slate-800 border-slate-300'}`}>
                  {activeTrial.status}
                </span>
              </div>

              <div>
                <span className="text-[10px] font-bold uppercase text-slate-500 block">IEC Approval</span>
                <span className={`inline-block border px-2 py-0.5 font-mono text-[10px] font-bold uppercase mt-0.5 ${activeTrial.ethics_approval_status === 'approved' ? 'bg-emerald-50 text-emerald-800 border-emerald-300' : 'bg-amber-50 text-amber-800 border-amber-300'}`}>
                  {activeTrial.ethics_approval_status || 'Pending'}
                </span>
              </div>

              <div>
                <span className="text-[10px] font-bold uppercase text-slate-500 block">CTRI Registration</span>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className={`font-mono text-[11px] font-semibold ${activeTrial.ctri_number ? 'text-slate-800' : 'text-amber-700'}`}>
                    {activeTrial.ctri_number || 'Missing (Rule 22)'}
                  </span>
                  <button
                    onClick={() => setShowCtriModal(true)}
                    className="border border-slate-300 bg-white px-1.5 py-0.5 text-[10px] font-bold text-slate-700 hover:bg-slate-100 transition shadow-xs"
                  >
                    {activeTrial.ctri_number ? 'Edit' : '+ Register CTRI'}
                  </button>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <label className="text-[11px] font-bold uppercase text-slate-700">
                Change Protocol Status:
              </label>
              <select
                value={activeTrial.status}
                disabled={statusBusy}
                onChange={(e) => handleQuickStatusChange(e.target.value)}
                className="border border-slate-400 bg-white p-1.5 text-xs font-bold text-slate-900 focus:border-slate-800 focus:outline-none"
              >
                <option value="planning">PLANNING (Drafting)</option>
                <option value="pending_ethics">PENDING_ETHICS (Under Review)</option>
                <option value="approved">APPROVED (IEC Cleared)</option>
                <option value="recruiting">RECRUITING (Open for Screening)</option>
                <option value="active">ACTIVE (Treatment Stage)</option>
                <option value="suspended">SUSPENDED (Safety Hold)</option>
                <option value="completed">COMPLETED (Closed)</option>
                <option value="terminated">TERMINATED (Early Exit)</option>
              </select>

              {activeTrial.status !== 'recruiting' && (
                <button
                  onClick={handleQuickActivate}
                  disabled={statusBusy}
                  className="border border-emerald-700 bg-emerald-700 px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-white hover:bg-emerald-800 transition shadow-sm disabled:opacity-50"
                >
                  🚀 Activate Recruitment
                </button>
              )}
            </div>
          </div>
        )}
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

      {showCreateTrialModal && (
        <CreateTrialModal
          onClose={() => setShowCreateTrialModal(false)}
          onSuccess={() => {
            loadTrials()
            props.onRefresh?.()
          }}
        />
      )}

      {showCtriModal && activeTrial && (
        <RegisterCtriModal
          trial={activeTrial}
          onClose={() => setShowCtriModal(false)}
          onSuccess={() => {
            loadTrials()
            props.onRefresh?.()
          }}
        />
      )}
    </div>
  )
}
