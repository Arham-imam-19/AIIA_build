import { useEffect, useState } from 'react'
import { createUser, fetchSites } from '../api'

// STRICT DELEGATED ADMINISTRATION ROLES FOR PRIMARY ADMIN
const AVAILABLE_ROLES = [
  {
    role: 'institution_admin',
    label: 'Institution Site Admin',
    desc: 'Hospital Site Administrator. Oversees hospital site research infrastructure and site personnel.',
    requiresSite: true,
  },
  {
    role: 'monitor',
    label: 'Monitor',
    desc: 'Independent auditor: performs Source Data Verification (SDV).',
    requiresSite: false,
  },

  {
    role: 'sponsor',
    label: 'Sponsor (Director / Funder)',
    desc: 'Trial Sponsor Unit. Oversees recruitment metrics, cross-site compliance, and data exports.',
    requiresSite: false,
  },
  {
    role: 'regulator',
    label: 'Regulator (CDSCO)',
    desc: 'Statutory Regulatory Authority. Full audit inspection access under 21 CFR Part 11 and NDCT Rules 2019.',
    requiresSite: false,
  },
  {
    role: 'pharmacovigilance',
    label: 'Pharmacovigilance (NPvCC)',
    desc: 'National Pharmacovigilance Coordination Centre. Monitors SAEs and SUSARs.',
    requiresSite: false,
  },
  {
    role: 'dsmb',
    label: 'Data and Safety Monitoring Board (DSMB)',
    desc: 'Independent Data and Safety Monitoring Board. Reviews unblinded safety and efficacy data.',
    requiresSite: false,
  },
]

export default function CreateUserPage({ onNavigateDashboard }) {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState(AVAILABLE_ROLES[0].role)
  const [siteId, setSiteId] = useState('')
  const [password, setPassword] = useState('AIIA@2026!')
  const [showPassword, setShowPassword] = useState(false)
  const [organization, setOrganization] = useState('')
  const [phone, setPhone] = useState('')
  const [sites, setSites] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [successMsg, setSuccessMsg] = useState(null)

  useEffect(() => {
    fetchSites()
      .then((res) => {
        if (res.items?.length) {
          setSites(res.items)
          setSiteId(res.items[0].id)
        }
      })
      .catch(() => {})
  }, [])

  const selectedRoleConfig = AVAILABLE_ROLES.find((r) => r.role === role)

  function generatePassword() {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%&*'
    let pwd = ''
    for (let i = 0; i < 12; i++) {
      pwd += chars.charAt(Math.floor(Math.random() * chars.length))
    }
    setPassword(pwd)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setSuccessMsg(null)

    try {
      await createUser({
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        role,
        password,
        site_id: selectedRoleConfig?.requiresSite && siteId ? Number(siteId) : undefined,
        organization: organization.trim() || undefined,
        phone: phone.trim() || undefined,
      })

      setSuccessMsg(`Account for "${fullName}" (${email}) successfully created with role "${selectedRoleConfig?.label}".`)
      setFullName('')
      setEmail('')
      setOrganization('')
      setPhone('')
      setPassword('AIIA@2026!')
    } catch (err) {
      setError(err.detail || err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Official Government Page Header */}
      <div className="border border-slate-300 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Government of India &middot; Ministry of Ayush &middot; AIIA CTMS Portal
            </div>
            <h2 className="mt-1 text-lg font-bold text-slate-900">
              User Account Provisioning & Role Allocation
            </h2>
            <p className="mt-0.5 text-xs text-slate-600">
              Official registration of Institution Administrators and Global Oversight Personnel (Sponsors, Regulators, NPvCC, DSMB). Local clinical staff must be provisioned by their respective Institution Site Admins.
            </p>
          </div>
          <button
            onClick={onNavigateDashboard}
            className="border border-slate-400 bg-slate-100 px-4 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-200"
          >
            &larr; Back to Admin Dashboard
          </button>
        </div>
      </div>

      {/* Success Notice */}
      {successMsg && (
        <div className="border border-emerald-600 bg-emerald-50 p-4 text-xs font-medium text-emerald-900">
          <div className="font-bold">STATUS: ACCOUNT CREATED SUCCESSFULLY</div>
          <p className="mt-1">{successMsg}</p>
          <div className="mt-3 flex gap-3">
            <button
              onClick={onNavigateDashboard}
              className="border border-emerald-700 bg-emerald-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-800"
            >
              View in User Directory &rarr;
            </button>
            <button
              onClick={() => setSuccessMsg(null)}
              className="border border-emerald-400 bg-white px-3 py-1.5 text-xs font-semibold text-emerald-800 hover:bg-emerald-100"
            >
              Create Another Account
            </button>
          </div>
        </div>
      )}

      {/* Error Notice */}
      {error && (
        <div className="border border-red-600 bg-red-50 p-4 text-xs font-medium text-red-900">
          <div className="font-bold">ERROR: ACCOUNT PROVISIONING FAILED</div>
          <p className="mt-1">{typeof error === 'string' ? error : JSON.stringify(error)}</p>
        </div>
      )}

      {/* Main Government Form */}
      <form onSubmit={handleSubmit} className="border border-slate-300 bg-white p-6 shadow-sm space-y-6 text-xs">
        
        {/* Section 1: User Identity */}
        <fieldset className="border border-slate-200 p-4">
          <legend className="px-2 font-bold uppercase tracking-wider text-slate-700 text-[11px]">
            1. Identity & Official Contact Details
          </legend>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
            <div>
              <label className="block font-semibold text-slate-800">
                Full Name (with Prefix/Title) <span className="text-red-600">*</span>
              </label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g. Dr. Rajesh Kumar Sharma"
                className="mt-1 w-full border border-slate-300 bg-white p-2.5 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
              <span className="text-[10px] text-slate-500">Official legal name as registered in clinical trial documentation.</span>
            </div>

            <div>
              <label className="block font-semibold text-slate-800">
                Official Institutional Email Address <span className="text-red-600">*</span>
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="e.g. rajesh.sharma@aiia-ctms.in"
                className="mt-1 w-full border border-slate-300 bg-white p-2.5 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
              <span className="text-[10px] text-slate-500">Must be an authorized hospital/institute email address.</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            <div>
              <label className="block font-semibold text-slate-800">
                Department / Institutional Division
              </label>
              <input
                type="text"
                value={organization}
                onChange={(e) => setOrganization(e.target.value)}
                placeholder="e.g. Department of Kayachikitsa, AIIA"
                className="mt-1 w-full border border-slate-300 bg-white p-2.5 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-800">
                Official Contact Mobile Number
              </label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+91 98765 43210"
                className="mt-1 w-full border border-slate-300 bg-white p-2.5 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>
          </div>
        </fieldset>

        {/* Section 2: Role & Jurisdiction */}
        <fieldset className="border border-slate-200 p-4">
          <legend className="px-2 font-bold uppercase tracking-wider text-slate-700 text-[11px]">
            2. Statutory Role & Site Jurisdiction Allocation
          </legend>

          <div className="mt-2">
            <label className="block font-semibold text-slate-800">
              Assigned Clinical Trial Role <span className="text-red-600">*</span>
            </label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="mt-1 w-full border border-slate-300 bg-white p-2.5 text-xs font-semibold text-slate-900 focus:border-slate-800 focus:outline-none"
            >
              {AVAILABLE_ROLES.map((r) => (
                <option key={r.role} value={r.role}>
                  {r.label}
                </option>
              ))}
            </select>
            {selectedRoleConfig && (
              <div className="mt-2 border-l-2 border-slate-600 bg-slate-50 p-2.5 text-[11px] text-slate-700">
                <strong>Statutory Scope:</strong> {selectedRoleConfig.desc}
              </div>
            )}
          </div>

          <div className="mt-4">
            <label className="block font-semibold text-slate-800">
              Designated Hospital / Research Site <span className="text-red-600">*</span>
            </label>
            <select
              value={selectedRoleConfig?.requiresSite ? siteId : ''}
              onChange={(e) => setSiteId(e.target.value)}
              disabled={!selectedRoleConfig?.requiresSite}
              className={`mt-1 w-full border border-slate-300 p-2.5 text-xs font-semibold text-slate-900 focus:border-slate-800 focus:outline-none ${
                !selectedRoleConfig?.requiresSite ? 'bg-slate-100 opacity-70 cursor-not-allowed' : 'bg-white'
              }`}
              required
            >
              {!selectedRoleConfig?.requiresSite && (
                <option value="">Global (Multi-Centric) - All Sites</option>
              )}
              {selectedRoleConfig?.requiresSite &&
                (() => {
                  const seen = new Set()
                  return sites
                    .filter((s) => {
                      if (seen.has(s.site_code)) return false
                      seen.add(s.site_code)
                      return true
                    })
                    .map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} (Site Code: {s.site_code}) &mdash; {s.city}, {s.state}
                      </option>
                    ))
                })()}
            </select>
          </div>
        </fieldset>

        {/* Section 3: Credentials */}
        <fieldset className="border border-slate-200 p-4">
          <legend className="px-2 font-bold uppercase tracking-wider text-slate-700 text-[11px]">
            3. Authentication Credentials
          </legend>
          
          <div className="mt-2">
            <label className="block font-semibold text-slate-800">
              Temporary Portal Password <span className="text-red-600">*</span>
            </label>
            <div className="mt-1 flex gap-2">
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border border-slate-300 bg-white p-2.5 text-xs font-mono text-slate-900 focus:border-slate-800 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="border border-slate-400 bg-slate-100 px-3 py-2 text-[11px] font-semibold text-slate-800 hover:bg-slate-200"
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
              <button
                type="button"
                onClick={generatePassword}
                className="border border-slate-800 bg-slate-900 px-3 py-2 text-[11px] font-semibold text-white hover:bg-black"
              >
                Generate
              </button>
            </div>
            <p className="mt-1.5 text-[10px] text-slate-500">
              The user will be required to change this temporary password upon first authentication to comply with 21 CFR Part 11 electronic signature rules.
            </p>
          </div>
        </fieldset>

        <div className="border-t border-slate-300 bg-slate-50 p-4 -mx-6 -mb-6 mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onNavigateDashboard}
            className="border border-slate-300 bg-white px-5 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy}
            className="border border-aiia-700 bg-aiia-600 px-5 py-2.5 text-xs font-bold uppercase tracking-wider text-white hover:bg-aiia-700 disabled:opacity-50"
          >
            {busy ? 'Provisioning Account...' : 'Provision User Account'}
          </button>
        </div>
      </form>
    </div>
  )
}
