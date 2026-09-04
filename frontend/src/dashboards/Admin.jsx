import { useEffect, useState } from 'react'
import { fetchSites, fetchUsers, fetchTrials, resetTrialData, updateUser, updateTrialStatus, activateTrial } from '../api'
import CreateTrialModal from '../components/CreateTrialModal'
import CreateSiteModal from '../components/CreateSiteModal'
import RegisterCtriModal from '../components/RegisterCtriModal'
import DashboardLayout from './layout'
import { Block } from '../blocks'

const ROLE_DISPLAY_NAMES = {
  admin: 'Primary System Administrator',
  institution_admin: 'Institution Site Admin',
  principal_investigator: 'Principal Investigator',
  coordinator: 'Clinical Research Coordinator',
  ethics_committee: 'Ethics Committee Member',
  sponsor: 'Trial Sponsor (Director / Funder)',
  regulator: 'CDSCO Regulatory Inspector',
  dsmb: 'Data and Safety Monitoring Board (DSMB)',
  pharmacovigilance: 'Pharmacovigilance Officer (NPvCC)',
  monitor: 'Clinical Trial Monitor (CRA)',
  patient: 'Enrolled Trial Participant',
}

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

function getGatesForTrial(trial) {
  if (!trial) return []
  const hasCtri = Boolean(trial.ctri_number && trial.ctri_number.trim())
  const hasEthics = trial.ethics_approval_status === 'approved'
  const hasRegulatory = Boolean(trial.regulatory_approval_number && trial.regulatory_approval_number.trim()) || trial.phase === 'phase_4'
  const isCovered = trial.status === 'active' || trial.status === 'recruiting' || trial.status === 'planning'

  return [
    {
      label: 'CTRI Registration (NDCT Rule 22)',
      ok: hasCtri,
      detail: hasCtri ? trial.ctri_number : 'Pending CTRI Registration',
    },
    {
      label: 'Ethics Committee Approval (Rule 22 & 42)',
      ok: hasEthics,
      detail: hasEthics
        ? trial.ethics_approval_number ? `Approved (${trial.ethics_approval_number})` : 'Approved'
        : `Pending Review (${trial.ethics_approval_status ? trial.ethics_approval_status.toUpperCase() : 'PENDING'})`,
    },
    {
      label: 'DCGI / Regulatory Clearance',
      ok: hasRegulatory,
      detail: hasRegulatory
        ? trial.regulatory_approval_number || 'Clearance Granted'
        : 'Awaiting DCGI Clearance',
    },
    {
      label: 'Clinical Trial Insurance & Status',
      ok: isCovered,
      detail: isCovered ? `Active (${trial.status ? trial.status.toUpperCase() : 'PLANNING'})` : 'Inactive',
    },
  ]
}

export default function Admin(props) {
  const [users, setUsers] = useState([])
  const [sites, setSites] = useState([])
  const [trials, setTrials] = useState([])
  const [selectedProtocolId, setSelectedProtocolId] = useState(null)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [siteFilter, setSiteFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [showTrialModal, setShowTrialModal] = useState(false)
  const [showSiteModal, setShowSiteModal] = useState(false)
  const [showCtriModal, setShowCtriModal] = useState(false)
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const [resettingUser, setResettingUser] = useState(null)
  const [newPassword, setNewPassword] = useState('')
  const [resetBusy, setResetBusy] = useState(false)
  const [resetMsg, setResetMsg] = useState(null)
  const [cleanSlateBusy, setCleanSlateBusy] = useState(false)
  const [cleanSlateResult, setCleanSlateResult] = useState(null)
  const [activeTab, setActiveTab] = useState('governance')
  const [statusBusy, setStatusBusy] = useState(false)
  const [statusMsg, setStatusMsg] = useState(null)
  const [statusErr, setStatusErr] = useState(null)

  function loadUsers() {
    setLoading(true)
    fetchUsers({
      search: search || undefined,
      role: roleFilter || undefined,
      site_id: siteFilter || undefined,
      limit: 100,
    })
      .then((res) => {
        setUsers((res.items || []).filter(u => u.role !== 'patient'))
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }

  function loadSites() {
    fetchSites()
      .then((res) => setSites(res.items || []))
      .catch(() => {})
  }

  function loadTrials() {
    fetchTrials()
      .then((res) => {
        const items = res.items || []
        setTrials(items)
        if (items.length > 0 && !selectedProtocolId) {
          setSelectedProtocolId(items[0].id)
        }
      })
      .catch(() => {})
  }

  useEffect(() => {
    loadUsers()
  }, [search, roleFilter, siteFilter])

  useEffect(() => {
    loadSites()
    loadTrials()
  }, [])

  const activeTrial = trials.find(t => t.id === selectedProtocolId) || trials[0]
  const activeGates = getGatesForTrial(activeTrial)

  const ndctBlock = {
    kind: 'checklist',
    key: 'ndct_gates',
    title: `NDCT Rules 2019 Gates - ${activeTrial?.protocol_number || 'Protocol Gates'}`,
    passed: activeGates.filter(g => g.ok).length,
    total: activeGates.length,
    items: activeGates,
  }

  const originalBlocks = props.dashboard?.blocks || []
  const auditBlock = originalBlocks.find(b => b.key === 'audit_tail')
  const auditLogs = auditBlock?.rows || []
  const auditColumns = auditBlock?.columns || []

  const uniqueSitesCount = new Set(sites.map((s) => s.site_code)).size
  const customTiles = [
    { key: 'total_protocols', label: 'Total Configured Protocols', value: trials.length, tone: 'neutral' },
    { key: 'missing_ctri', label: 'Protocols Missing CTRI', value: trials.filter(t => !t.ctri_number).length, tone: 'warn' },
    { key: 'total_sites', label: 'Total Active Sites', value: uniqueSitesCount, tone: 'good' },
    { key: 'audit_entries', label: 'System Audit Entries', value: props.dashboard?.tiles?.find(t => t.key === 'audit_entries')?.value || auditLogs.length || 0, tone: 'neutral' },
  ]

  const genericTab1Blocks = originalBlocks.filter(b => !['audit_tail', 'sae_reporting', 'sites'].includes(b.key))
  const tab2Blocks = originalBlocks.filter(b => ['sites'].includes(b.key))

  async function handleCleanSlateReset() {
    setCleanSlateBusy(true)
    setCleanSlateResult(null)
    try {
      const res = await resetTrialData()
      setCleanSlateResult(res)
      loadUsers()
      loadTrials()
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
      setResetMsg('Password successfully updated!')
      setNewPassword('')
      setTimeout(() => {
        setResettingUser(null)
        setResetMsg(null)
      }, 1500)
    } catch (err) {
      setResetMsg(`Failed to update password: ${err.message}`)
    } finally {
      setResetBusy(false)
    }
  }

  async function handleQuickStatusChange(newStatus) {
    if (!activeTrial) return
    setStatusBusy(true)
    setStatusErr(null)
    setStatusMsg(null)
    try {
      await updateTrialStatus(activeTrial.id, {
        status: newStatus,
        reason: `Status transitioned to ${newStatus} by IT Administrator.`
      })
      setStatusMsg(`Protocol ${activeTrial.protocol_number} status transitioned to ${newStatus.toUpperCase()}`)
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
          reason: 'Protocol recruitment activated by IT Administrator.'
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

      {/* Toast notifications */}
      {statusMsg && (
        <div className="fixed top-4 right-4 z-50 animate-bounce">
          <div className="bg-emerald-700 text-white px-5 py-3 shadow-xl text-xs font-semibold flex items-center gap-3">
            <span>✅</span> {statusMsg}
          </div>
        </div>
      )}

      {statusErr && (
        <div className="fixed top-4 right-4 z-50">
          <div className="bg-red-700 text-white px-5 py-3 shadow-xl text-xs font-semibold flex items-center gap-3">
            <span>⚠️</span> {statusErr}
            <button onClick={() => setStatusErr(null)} className="ml-2 font-bold hover:text-red-200">✕</button>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-slate-300 bg-white shadow-sm">
        <button
          onClick={() => setActiveTab('governance')}
          className={`px-5 py-3 text-[11px] font-bold uppercase tracking-wider transition ${activeTab === 'governance' ? 'border-b-2 border-slate-900 text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}
        >
          🏛️ System Governance &amp; Protocols
        </button>
        <button
          onClick={() => setActiveTab('personnel')}
          className={`px-5 py-3 text-[11px] font-bold uppercase tracking-wider transition ${activeTab === 'personnel' ? 'border-b-2 border-slate-900 text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}
        >
          👥 Personnel &amp; Sites
        </button>
        <button
          onClick={() => setActiveTab('advanced')}
          className={`px-5 py-3 text-[11px] font-bold uppercase tracking-wider transition ${activeTab === 'advanced' ? 'border-b-2 border-slate-900 text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}
        >
          ⚙️ Advanced Actions &amp; Clean Slate
        </button>
      </div>

      <div className="space-y-6 pt-4">
        {activeTab === 'governance' && (
          <>
            <DashboardLayout
              {...props}
              dashboard={{ 
                ...props.dashboard, 
                tiles: customTiles,
                blocks: [] 
              }}
              note="Central Regulatory Oversight: The Primary Administrator has statutory administrative access across all participating sites under 21 CFR Part 11 and NDCT Rules 2019."
            />

            {/* Protocol Governance & Status Transition Bar */}
            <div className="border border-slate-300 bg-white p-4 shadow-sm space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
                <div className="w-full max-w-lg">
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-700 mb-1">
                    Select Target Trial Protocol
                  </label>
                  <select
                    value={selectedProtocolId || ''}
                    onChange={e => setSelectedProtocolId(Number(e.target.value))}
                    disabled={trials.length === 0}
                    className="w-full border border-slate-300 p-2 text-xs font-semibold text-slate-900 focus:border-slate-800 focus:outline-none"
                  >
                    {trials.length === 0 ? (
                      <option value="">No Protocols Configured (Click + Register New Protocol)</option>
                    ) : (
                      trials.map(p => (
                        <option key={p.id} value={p.id}>
                          [{p.protocol_number}] {p.short_title || p.title} &middot; Status: {p.status?.toUpperCase()}
                        </option>
                      ))
                    )}
                  </select>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowTrialModal(true)}
                    className="border border-slate-800 bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-black transition shadow-sm"
                  >
                    + Register New Protocol
                  </button>
                </div>
              </div>

              {trials.length === 0 && (
                <div className="border border-blue-200 bg-blue-50 p-4 text-xs text-blue-900 flex items-center justify-between">
                  <div>
                    <strong className="font-bold">No Active Protocols:</strong> The CTMS is currently in a clean slate state. Click <strong>+ Register New Protocol</strong> above to configure your first clinical trial protocol and assign participating hospital institutions.
                  </div>
                </div>
              )}

              {/* Protocol Lifecycle Status Transition Controls */}
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

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Block block={ndctBlock} wide={true} />
              
              {/* Custom Audit Logs Table with Role Filter */}
              {auditBlock && (
                <div className="col-span-full rounded-none border border-slate-300 bg-white p-5 shadow-sm">
                  <h3 className="mb-1 text-sm font-bold text-slate-800">{auditBlock.title || 'System Access Audit Log'}</h3>
                  <p className="mb-4 text-xs text-slate-500">{auditBlock.note || '21 CFR Part 11 Compliant Electronic Audit Trail.'}</p>
                  <div className="-mx-1 overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-left text-[11px] font-bold uppercase tracking-wide text-slate-600 bg-slate-100 border-b border-slate-200">
                          {auditColumns.map(col => (
                            <th key={col.key} className="whitespace-nowrap px-3 py-2">
                              {col.label}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {auditLogs
                          .filter(log => ['admin', 'institution admin', 'institution site admin', 'sponsor', 'pharmacovigilance', 'regulator', 'monitor'].includes((log.role || '').toLowerCase()))
                          .map((log, index) => (
                          <tr key={index} className="hover:bg-slate-50">
                            {auditColumns.map(col => (
                              <td key={col.key} className="px-3 py-2 text-slate-700 font-mono text-[11px]" style={{ maxWidth: '22rem' }}>
                                {log[col.key]}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </>
        )}

        {/* Tab 2: Personnel & Sites */}
        {activeTab === 'personnel' && (
        <div className="space-y-6">
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
                  onClick={() => setShowTrialModal(true)}
                  className="border border-slate-600 bg-white px-4 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-50 transition"
                >
                  + Register Protocol
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
                    {(() => {
                      const seen = new Set()
                      return sites
                        .filter((s) => {
                          if (seen.has(s.site_code)) return false
                          seen.add(s.site_code)
                          return true
                        })
                        .map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.name} ({s.site_code})
                          </option>
                        ))
                    })()}
                  </select>
                </div>
              </div>

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
                      users.filter(u => u.role !== 'patient').map((u) => (
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
            dashboard={{ ...props.dashboard, tiles: [], blocks: tab2Blocks }}
            wide={['sites']}
          />
        </div>
      )}

      {/* Tab 3: Advanced Actions & Clean Slate */}
      {activeTab === 'advanced' && (
        <div className="space-y-6">
          <div className="border border-slate-300 bg-white p-6 shadow-sm">
            <h3 className="text-sm font-bold text-slate-900 border-b border-slate-200 pb-2">
              Production Data Reset &amp; Clean Slate Control
            </h3>
            <p className="text-xs text-slate-600 mt-2 leading-relaxed">
              Administrative action to clear all synthetic participant records, clinical progress logs, study visits, and adverse events across all sites and trials to prepare the CTMS portal for 100% real subject intake.
            </p>
            <button 
              onClick={() => setShowResetConfirm(true)} 
              className="mt-4 border border-red-700 bg-red-700 px-5 py-2.5 text-xs font-bold text-white hover:bg-red-800 transition"
            >
              Execute Clean Slate Reset
            </button>
          </div>
        </div>
      )}
      </div>

      {/* Create Trial Modal */}
      {showTrialModal && (
        <CreateTrialModal
          onClose={() => setShowTrialModal(false)}
          onSuccess={() => {
            loadSites()
            loadTrials()
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

      {/* Register CTRI Modal */}
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
              This administrative action executes a complete system purge, deleting all protocols, registered hospital institutions, local staff accounts (PI, Coordinator, Institution Admin), patient records, visits, and clinical progress logs.
            </p>

            {cleanSlateResult ? (
              <div className="mt-4 border border-emerald-600 bg-emerald-50 p-4 text-xs text-emerald-900 space-y-2">
                <p className="font-bold">CLEAN SLATE RESET COMPLETED SUCCESSFULLY</p>
                <p>&bull; Cleared {cleanSlateResult.cleared_trials || 0} protocol definitions.</p>
                <p>&bull; Cleared {cleanSlateResult.cleared_sites || 0} hospital &amp; institution sites.</p>
                <p>&bull; Cleared {cleanSlateResult.cleared_accounts || 0} site-level accounts (PI, CRC, Institution Admin, Patients).</p>
                <p>&bull; Cleared {cleanSlateResult.cleared_subjects || 0} participant dossiers.</p>
                <p>&bull; Cleared {cleanSlateResult.cleared_visits || 0} study visit records.</p>
                <p>&bull; Cleared {cleanSlateResult.cleared_clinical_logs || 0} clinical progress logs.</p>
                <p>&bull; Cleared {cleanSlateResult.cleared_adverse_events || 0} adverse events.</p>
                <p>&bull; Cleared {cleanSlateResult.cleared_econsents || 0} electronic consents.</p>
                <p>&bull; Preserved {cleanSlateResult.preserved_accounts || 7} global oversight accounts (IT Admin, Monitor, Sponsor, Ethics, Pharmacovigilance, Regulator, DSMB).</p>
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
                  <strong>Notice:</strong> All protocols, hospital sites, local investigator &amp; coordinator accounts, participant records, visits, and clinical logs will be permanently deleted. Only core global oversight accounts (IT Admin, Monitor, Sponsor, Ethics, Pharmacovigilance, Regulator, DSMB) and 21 CFR Part 11 audit trails will be preserved.
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
