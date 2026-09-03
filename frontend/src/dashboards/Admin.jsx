import { useEffect, useState } from 'react'
import { fetchSites, fetchUsers, resetTrialData, updateUser } from '../api'
import CreateTrialModal from '../components/CreateTrialModal'
import CreateSiteModal from '../components/CreateSiteModal'
import DataExportCenter from '../components/DataExportCenter'
import DashboardLayout from './layout'

const ROLE_DISPLAY_NAMES = {
  admin: 'Primary Administrator',
  institution_admin: 'Institution Site Admin',
  principal_investigator: 'Principal Investigator',
  coordinator: 'Clinical Research Coordinator',
  ethics_committee: 'Ethics Committee Member',
  sponsor: 'Trial Sponsor / Monitor',
  regulator: 'CDSCO Regulatory Inspector',
  patient: 'Subject / Patient',
}

export default function Admin(props) {
  const [users, setUsers] = useState([])
  const [sites, setSites] = useState([])
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [siteFilter, setSiteFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [showTrialModal, setShowTrialModal] = useState(false)
  const [showSiteModal, setShowSiteModal] = useState(false)
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const [resettingUser, setResettingUser] = useState(null)
  const [newPassword, setNewPassword] = useState('')
  const [resetBusy, setResetBusy] = useState(false)
  const [resetMsg, setResetMsg] = useState(null)
  const [cleanSlateBusy, setCleanSlateBusy] = useState(false)
  const [cleanSlateResult, setCleanSlateResult] = useState(null)

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

  function loadSites() {
    fetchSites()
      .then((res) => setSites(res.items || []))
      .catch(() => {})
  }

  useEffect(() => {
    loadUsers()
  }, [search, roleFilter, siteFilter])

  useEffect(() => {
    loadSites()
  }, [])

  async function handleCleanSlateReset() {
    setCleanSlateBusy(true)
    setCleanSlateResult(null)
    try {
      const res = await resetTrialData()
      setCleanSlateResult(res)
      loadUsers()
      props.onRefresh?.()
    } catch (err) {
      alert(`Clean slate reset failed: ${err.message}`)
    } finally {
      setCleanSlateBusy(false)
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

  async function handleResetPassword(e) {
    e.preventDefault()
    if (!resettingUser || !newPassword) return
    setResetBusy(true)
    setResetMsg(null)
    try {
      await updateUser(resettingUser.id, { password: newPassword })
      setResetMsg('Password successfully updated.')
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
    <div className="space-y-6">
      {/* Official Government Banner */}
      <div className="border border-slate-300 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Government of India &middot; Ministry of Ayush &middot; Central CTMS Unit
            </div>
            <h2 className="text-sm font-bold text-slate-900 mt-0.5">
              Primary Administrator &mdash; Central Oversight &amp; User Provisioning Control Plane
            </h2>
          </div>
          <div className="text-right text-[11px] font-mono text-slate-500">
            Jurisdiction: Global / All Sites &middot; 21 CFR Part 11 Active
          </div>
        </div>
      </div>

      {/* Official Quick Action Bar */}
      <div className="border border-slate-300 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4">
          <div>
            <h3 className="text-sm font-bold uppercase tracking-wide text-slate-900">
              Primary Administrator Operations Center
            </h3>
            <p className="text-xs text-slate-600 mt-0.5">
              Manage authorized personnel accounts, inspect trial sites, and coordinate clinical infrastructure.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => props.onNavigateCreateUser?.()}
              className="border border-slate-800 bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-black transition"
            >
              + Create New Account
            </button>
            <button
              onClick={() => props.onNavigateInfrastructure?.()}
              className="border border-slate-400 bg-slate-100 px-4 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-200 transition"
            >
              Clinical Infrastructure &amp; Actions &rarr;
            </button>
            <button
              onClick={() => setShowResetConfirm(true)}
              className="border border-red-500 bg-red-50 px-4 py-2 text-xs font-semibold text-red-800 hover:bg-red-100 transition"
            >
              Reset Test Data (Clean Slate)
            </button>
          </div>
        </div>

        {/* User Account Management Directory */}
        <div className="mt-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                Authorized Personnel Roster ({users.length} Registered Accounts)
              </h4>
              <p className="text-[11px] text-slate-500">
                Live registry of clinicians, coordinators, ethicists, sponsors, and statutory monitors.
              </p>
            </div>
            <button
              onClick={() => props.onNavigateCreateUser?.()}
              className="border border-slate-400 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-800 hover:bg-slate-100"
            >
              + Add User
            </button>
          </div>

          {/* Filters */}
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Search User</label>
              <input
                type="text"
                placeholder="Search by name or email..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Filter by Role</label>
              <select
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
                className="w-full border border-slate-300 bg-white p-2 text-xs font-medium text-slate-900 focus:border-slate-800 focus:outline-none"
              >
                <option value="">All Roles (Total: {users.length})</option>
                {Object.entries(ROLE_DISPLAY_NAMES).map(([r, label]) => (
                  <option key={r} value={r}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Filter by Study Site</label>
              <select
                value={siteFilter}
                onChange={(e) => setSiteFilter(e.target.value)}
                className="w-full border border-slate-300 bg-white p-2 text-xs font-medium text-slate-900 focus:border-slate-800 focus:outline-none"
              >
                <option value="">All Participating Sites</option>
                {sites.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.site_code})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* User Table */}
          <div className="mt-4 border border-slate-300 overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-slate-100 border-b border-slate-300 text-[11px] font-bold uppercase tracking-wider text-slate-700">
                <tr>
                  <th className="border-r border-slate-300 px-3.5 py-2.5">Name &amp; Official Email</th>
                  <th className="border-r border-slate-300 px-3.5 py-2.5">Statutory Role</th>
                  <th className="border-r border-slate-300 px-3.5 py-2.5">Designated Center</th>
                  <th className="border-r border-slate-300 px-3.5 py-2.5">Account Status</th>
                  <th className="border-r border-slate-300 px-3.5 py-2.5">Last Authentication</th>
                  <th className="px-3.5 py-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                      Loading user directory from database...
                    </td>
                  </tr>
                ) : users.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                      No registered user accounts match the selected criteria.
                    </td>
                  </tr>
                ) : (
                  users.map((u) => (
                    <tr key={u.id} className="hover:bg-slate-50">
                      <td className="border-r border-slate-200 px-3.5 py-2.5">
                        <div className="font-bold text-slate-900">
                          {u.full_name}
                        </div>
                        <div className="font-mono text-[11px] text-slate-600">
                          {u.email}
                        </div>
                        {u.organization && (
                          <div className="text-[10px] text-slate-500">
                            {u.organization}
                          </div>
                        )}
                      </td>
                      <td className="border-r border-slate-200 px-3.5 py-2.5 font-semibold text-slate-800">
                        {ROLE_DISPLAY_NAMES[u.role] || u.role}
                      </td>
                      <td className="border-r border-slate-200 px-3.5 py-2.5 text-slate-700">
                        {u.site_id ? siteMap[u.site_id] || `Site #${u.site_id}` : 'Global (Multi-Centric)'}
                      </td>
                      <td className="border-r border-slate-200 px-3.5 py-2.5">
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
                      <td className="border-r border-slate-200 px-3.5 py-2.5 font-mono text-[11px] text-slate-600">
                        {u.last_login_at
                          ? new Date(u.last_login_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })
                          : 'Never'}
                      </td>
                      <td className="px-3.5 py-2.5 text-right">
                        <button
                          onClick={() => setResettingUser(u)}
                          className="border border-slate-400 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-800 hover:bg-slate-100"
                        >
                          Reset Password
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <DashboardLayout
        {...props}
        wide={['recent_aes', 'upcoming']}
        note="Central Regulatory Oversight: The Primary Administrator has statutory administrative access across all participating sites under 21 CFR Part 11 and NDCT Rules 2019."
      />

      <DataExportCenter />

      {/* Create Trial Modal */}
      {showTrialModal && (
        <CreateTrialModal
          onClose={() => setShowTrialModal(false)}
          onSuccess={() => {
            loadSites()
            props.onRefresh?.()
          }}
        />
      )}

      {/* Create Site Modal */}
      {showSiteModal && (
        <CreateSiteModal
          onClose={() => setShowSiteModal(false)}
          onSuccess={() => {
            loadSites()
            props.onRefresh?.()
          }}
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
                <p>&bull; Cleared {cleanSlateResult.cleared_adverse_events} adverse events.</p>
                <p>&bull; Preserved all registered hospital sites, user accounts, and 21 CFR Part 11 audit trails.</p>
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
                  <strong>Notice:</strong> All synthetic participant records, visits, adverse events, and e-consents will be permanently purged. Core trial definitions, registered hospital sites, user login accounts, and statutory audit logs will be preserved.
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

      {/* Password Reset Modal */}
      {resettingUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4">
          <div className="w-full max-w-md border border-slate-400 bg-white p-6 shadow-xl">
            <h3 className="text-base font-bold text-slate-900 border-b border-slate-200 pb-2">
              Reset Password: {resettingUser.full_name}
            </h3>
            <p className="text-xs text-slate-600 mt-2">
              Enter a new secure password for {resettingUser.email}.
            </p>

            {resetMsg && (
              <div className="mt-3 border border-blue-400 bg-blue-50 p-2.5 text-xs text-blue-900">
                {resetMsg}
              </div>
            )}

            <form onSubmit={handleResetPassword} className="mt-4 space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-800">
                  New Password <span className="text-red-600">*</span>
                </label>
                <input
                  type="password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter new password"
                  className="mt-1 w-full border border-slate-300 bg-white p-2 font-mono text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setResettingUser(null)}
                  className="border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={resetBusy}
                  className="border border-slate-800 bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-black disabled:opacity-50"
                >
                  {resetBusy ? 'Updating...' : 'Update Password'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Clean Slate Confirmation Modal */}
      {showResetConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4">
          <div className="w-full max-w-lg border border-slate-400 bg-white p-6 shadow-xl">
            <h3 className="text-base font-bold text-slate-900 border-b border-slate-200 pb-2">
              Confirm Production Clean Slate Reset
            </h3>
            <p className="text-xs text-slate-600 mt-2">
              This administrative action clears all synthetic participant records, running clinical progress logs, study visits, and adverse events across all sites and trials to prepare the CTMS portal for 100% real subject intake.
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
