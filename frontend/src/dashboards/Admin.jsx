import { useEffect, useState } from 'react'
import { fetchSites, fetchUsers, updateUser } from '../api'
import CreateUserModal from '../components/CreateUserModal'
import DataExportCenter from '../components/DataExportCenter'
import DashboardLayout from './layout'

const ROLE_BADGE_STYLES = {
  admin: 'bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300',
  institution_admin: 'bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-300',
  principal_investigator: 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300',
  coordinator: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
  ethics_committee: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
  sponsor: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300',
  regulator: 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300',
  patient: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300',
}

const ROLE_DISPLAY_NAMES = {
  admin: 'Primary Admin',
  institution_admin: 'Institution Admin',
  principal_investigator: 'Principal Investigator',
  coordinator: 'Clinical Coordinator',
  ethics_committee: 'Ethics Committee',
  sponsor: 'Sponsor / Monitor',
  regulator: 'CDSCO Regulator',
  patient: 'Patient Subject',
}

export default function Admin(props) {
  const [users, setUsers] = useState([])
  const [sites, setSites] = useState([])
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [siteFilter, setSiteFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [resettingUser, setResettingUser] = useState(null)
  const [newPassword, setNewPassword] = useState('')
  const [resetBusy, setResetBusy] = useState(false)
  const [resetMsg, setResetMsg] = useState(null)

  function loadUsers() {
    setLoading(true)
    fetchUsers({
      search: search || undefined,
      role: roleFilter || undefined,
      site_id: siteFilter || undefined,
      limit: 100,
    })
      .then((res) => {
        setUsers(res.items || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }

  useEffect(() => {
    loadUsers()
  }, [search, roleFilter, siteFilter])

  useEffect(() => {
    fetchSites()
      .then((res) => setSites(res.items || []))
      .catch(() => {})
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

  async function handleResetPassword(e) {
    e.preventDefault()
    if (!resettingUser || !newPassword) return
    setResetBusy(true)
    setResetMsg(null)
    try {
      await updateUser(resettingUser.id, { password: newPassword })
      setResetMsg('Password successfully updated!')
      setTimeout(() => {
        setResettingUser(null)
        setNewPassword('')
        setResetMsg(null)
      }, 1500)
    } catch (err) {
      setResetMsg(`Error: ${err.message}`)
    } finally {
      setResetBusy(false)
    }
  }

  const siteMap = Object.fromEntries(sites.map((s) => [s.id, s.name]))

  return (
    <div className="space-y-5">
      {/* Primary Admin Banner */}
      <div className="flex items-center justify-between rounded-xl border border-purple-200 bg-purple-50/70 px-4 py-3 text-xs text-purple-900 dark:border-purple-900/50 dark:bg-purple-950/40 dark:text-purple-200">
        <span className="flex items-center gap-2 font-medium">
          <span className="flex h-2.5 w-2.5 rounded-full bg-purple-600"></span>
          👑 Primary System Administrator: Master User Provisioning & 21 CFR Part 11 Audit Control
        </span>
        <span className="hidden sm:inline font-mono text-[11px]">
          Global Scope &middot; Unrestricted Access
        </span>
      </div>

      {/* User Management & Account Provisioning Panel */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4 dark:border-slate-800">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              👥 System User Accounts & Access Control
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Create, configure, and manage user accounts across all clinical trial roles.
            </p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-1.5 rounded-lg bg-aiia-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-aiia-700 transition"
          >
            ➕ Create New User Account
          </button>
        </div>

        {/* Filters */}
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
          <input
            type="text"
            placeholder="🔍 Search name or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
          />
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="rounded-lg border border-slate-200 p-2 text-xs font-medium text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
          >
            <option value="">All Roles (Total: {users.length})</option>
            {Object.entries(ROLE_DISPLAY_NAMES).map(([r, label]) => (
              <option key={r} value={r}>
                {label}
              </option>
            ))}
          </select>
          <select
            value={siteFilter}
            onChange={(e) => setSiteFilter(e.target.value)}
            className="rounded-lg border border-slate-200 p-2 text-xs font-medium text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
          >
            <option value="">All Hospital Sites</option>
            {sites.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.site_code})
              </option>
            ))}
          </select>
        </div>

        {/* Users Table */}
        <div className="mt-4 overflow-x-auto rounded-xl border border-slate-100 dark:border-slate-800">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
              <tr>
                <th className="px-4 py-3">User & Contact</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Assigned Site</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Last Login</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                    Loading accounts...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                    No user accounts match the selected filters.
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                    <td className="px-4 py-3">
                      <div className="font-bold text-slate-900 dark:text-white">
                        {u.full_name}
                      </div>
                      <div className="font-mono text-[11px] text-slate-500">
                        {u.email}
                      </div>
                      {u.organization && (
                        <div className="text-[10px] text-slate-400">
                          {u.organization}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${
                          ROLE_BADGE_STYLES[u.role] || 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        {ROLE_DISPLAY_NAMES[u.role] || u.role}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                      {u.site_id ? siteMap[u.site_id] || `Site #${u.site_id}` : 'Global (Multi-site)'}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleToggleActive(u)}
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          u.is_active
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                            : 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300'
                        }`}
                      >
                        {u.is_active ? 'Active' : 'Deactivated'}
                      </button>
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-slate-500">
                      {u.last_login_at
                        ? new Date(u.last_login_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })
                        : 'Never'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setResettingUser(u)}
                        className="rounded-lg border border-slate-200 px-2.5 py-1 text-[11px] font-medium text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                      >
                        🔑 Reset Password
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <DashboardLayout
        {...props}
        wide={['recent_aes', 'upcoming']}
        note="Global Oversight: As Primary Administrator, you have full audit and operational access across all trial sites."
      />

      <DataExportCenter />

      {/* Create User Modal */}
      {showCreateModal && (
        <CreateUserModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            loadUsers()
            props.onRefresh?.()
          }}
        />
      )}

      {/* Password Reset Modal */}
      {resettingUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900">
            <h3 className="text-base font-bold text-slate-900 dark:text-white">
              Reset Password: {resettingUser.full_name}
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Enter a new secure password for {resettingUser.email}.
            </p>

            {resetMsg && (
              <div className="mt-3 rounded-lg bg-blue-50 p-2.5 text-xs text-blue-800 dark:bg-blue-950 dark:text-blue-200">
                {resetMsg}
              </div>
            )}

            <form onSubmit={handleResetPassword} className="mt-4 space-y-4 text-xs">
              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300">
                  New Password
                </label>
                <input
                  type="password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter new password"
                  className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs font-mono text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setResettingUser(null)}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={resetBusy}
                  className="rounded-lg bg-aiia-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-aiia-700 disabled:opacity-50"
                >
                  {resetBusy ? 'Updating...' : 'Update Password'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
