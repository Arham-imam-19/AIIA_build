import { useEffect, useState } from 'react'
import { createUser, fetchSites } from '../api'

const AVAILABLE_ROLES = [
  {
    role: 'principal_investigator',
    label: 'Principal Investigator (PI)',
    desc: 'Lead clinical physician. Full clinical write & patient management at assigned site.',
    requiresSite: true,
  },
  {
    role: 'coordinator',
    label: 'Clinical Research Coordinator (CRC)',
    desc: 'Day-to-day study coordinator. Schedules visits, patient intake, and data entry.',
    requiresSite: true,
  },
  {
    role: 'institution_admin',
    label: 'Institution Site Administrator',
    desc: 'Hospital administrator. Manages hospital personnel and oversees site recruitment.',
    requiresSite: true,
  },
  {
    role: 'ethics_committee',
    label: 'Institutional Ethics Committee (IEC)',
    desc: 'Independent safety reviewer. Inspects safety events, deviations, and ethical compliance.',
    requiresSite: false,
  },
  {
    role: 'sponsor',
    label: 'Trial Sponsor / Clinical Monitor (CRA)',
    desc: 'Trial oversight & monitoring. Monitors multi-site progress, SDTM/FHIR data exports.',
    requiresSite: false,
  },
  {
    role: 'regulator',
    label: 'Regulatory Inspector (CDSCO / Ayush)',
    desc: 'National regulatory body. Read-only audit across all trial sites and 21 CFR trails.',
    requiresSite: false,
  },
  {
    role: 'admin',
    label: 'Primary System Administrator',
    desc: 'Full administrative access across all system settings, user roles, and security policies.',
    requiresSite: false,
  },
]

export default function CreateUserModal({ onClose, onSuccess }) {
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
      onSuccess?.()
      onClose()
    } catch (err) {
      setError(err.detail || err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 dark:border-slate-800">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              👤 Create & Provision User Account
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Primary Administrator RBAC Provisioning & 21 CFR Part 11 Audit Trail
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="mt-3 rounded-lg bg-red-50 p-3 text-xs font-medium text-red-700 dark:bg-red-950 dark:text-red-300">
            {typeof error === 'string' ? error : JSON.stringify(error)}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Full Name
              </label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g. Dr. Ramesh Sharma"
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Official Email Address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="e.g. ramesh.sharma@aiia-ctms.in"
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
          </div>

          <div>
            <label className="block font-medium text-slate-700 dark:text-slate-300">
              Assigned Trial Role & Permissions
            </label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs font-medium text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            >
              {AVAILABLE_ROLES.map((r) => (
                <option key={r.role} value={r.role}>
                  {r.label}
                </option>
              ))}
            </select>
            {selectedRoleConfig && (
              <p className="mt-1 text-[11px] text-slate-500 italic">
                {selectedRoleConfig.desc}
              </p>
            )}
          </div>

          {selectedRoleConfig?.requiresSite && (
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Assigned Hospital / Institution Site
              </label>
              <select
                value={siteId}
                onChange={(e) => setSiteId(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs font-medium text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                required
              >
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
                        {s.name} ({s.site_code}) — {s.city}
                      </option>
                    ))
                })()}
              </select>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Department / Institution
              </label>
              <input
                type="text"
                value={organization}
                onChange={(e) => setOrganization(e.target.value)}
                placeholder="e.g. Dept of Kayachikitsa, AIIA"
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Official Phone Number
              </label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+91 98765 43210"
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 dark:border-slate-800 dark:bg-slate-800/40">
            <div className="flex items-center justify-between">
              <label className="font-bold text-xs text-slate-900 dark:text-white">
                Initial Password & Authentication Credential
              </label>
              <button
                type="button"
                onClick={generatePassword}
                className="text-[11px] font-semibold text-aiia-600 hover:text-aiia-700 dark:text-aiia-400"
              >
                🎲 Generate Secure
              </button>
            </div>
            <div className="mt-1.5 flex items-center gap-2">
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-slate-200 p-2 text-xs font-mono text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="rounded-lg border border-slate-200 px-2.5 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
            <p className="mt-1 text-[10px] text-slate-500">
              Passwords will be securely hashed with Argon2/BCrypt before storage.
            </p>
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-aiia-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-aiia-700 disabled:opacity-50"
            >
              {busy ? 'Creating Account...' : 'Create User Account'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
