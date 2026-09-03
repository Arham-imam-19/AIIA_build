import re

with open('frontend/src/dashboards/Admin.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Exclude patient roles from users
content = content.replace(
    "setUsers(res.items || [])",
    "setUsers((res.items || []).filter(u => u.role !== 'patient'))"
)

# 2. Add activeTab state
content = content.replace(
    "const [cleanSlateResult, setCleanSlateResult] = useState(null)",
    "const [cleanSlateResult, setCleanSlateResult] = useState(null)\n  const [activeTab, setActiveTab] = useState('governance')\n\n  const tab1Blocks = props.dashboard?.blocks?.filter(b => ['ndct_gates', 'audit_tail', 'sae_reporting'].includes(b.key)) || []\n  const tab2Blocks = props.dashboard?.blocks?.filter(b => ['sites'].includes(b.key)) || []"
)

# 3. Rewrite the return block
new_return = '''
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

      {/* Tabs */}
      <div className="flex border-b border-slate-300 bg-white shadow-sm">
        <button
          onClick={() => setActiveTab('governance')}
          className={px-5 py-3 text-[11px] font-bold uppercase tracking-wider }
        >
          System Governance
        </button>
        <button
          onClick={() => setActiveTab('personnel')}
          className={px-5 py-3 text-[11px] font-bold uppercase tracking-wider }
        >
          Personnel & Sites
        </button>
        <button
          onClick={() => setActiveTab('advanced')}
          className={px-5 py-3 text-[11px] font-bold uppercase tracking-wider }
        >
          Advanced Actions
        </button>
      </div>

      {activeTab === 'governance' && (
        <div className="space-y-6">
          <DashboardLayout
            {...props}
            dashboard={{ ...props.dashboard, blocks: tab1Blocks }}
            wide={['audit_tail', 'ndct_gates']}
            note="Central Regulatory Oversight: The Primary Administrator has statutory administrative access across all participating sites under 21 CFR Part 11 and NDCT Rules 2019."
          />
          <DataExportCenter />
        </div>
      )}

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
                  onClick={() => props.onNavigateInfrastructure?.()}
                  className="border border-slate-400 bg-slate-100 px-4 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-200 transition"
                >
                  Clinical Infrastructure &amp; Actions &rarr;
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
                    {sites.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} ({s.site_code})
                      </option>
                    ))}
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
                            {u.site_id ? siteMap[u.site_id] || Site # : 'Global (Multi-Centric)'}
                          </td>
                          <td className="border-r border-slate-200 px-3.5 py-2.5">
                            <button
                              onClick={() => handleToggleActive(u)}
                              className={order px-2.5 py-0.5 text-[10px] font-bold uppercase }
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

      {activeTab === 'advanced' && (
        <div className="space-y-6">
          <div className="border border-slate-300 bg-white p-6 shadow-sm">
            <h3 className="text-sm font-bold text-slate-900 border-b border-slate-200 pb-2">Production Data Reset &amp; Clean Slate Control</h3>
            <p className="text-xs text-slate-600 mt-2">Administrative action to clear synthetic records.</p>
            <button onClick={() => setShowResetConfirm(true)} className="mt-4 border border-red-700 bg-red-700 px-4 py-2 text-xs font-semibold text-white hover:bg-red-800 transition">
              Execute Clean Slate Reset
            </button>
          </div>
        </div>
      )}

      {/* Create Trial Modal */}
'''

start_idx = content.find("  return (")
end_idx = content.find("      {/* Create Trial Modal */}")
if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_return + content[end_idx+34:]

with open('frontend/src/dashboards/Admin.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
