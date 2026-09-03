// Ethics Committee: the independent body that approves the trial and reviews safety.
// Interactive IEC Protocol Review, Ethics Decision Workflow, and Oversight under NDCT Rules 2019.

import { useEffect, useState } from 'react'
import { fetchTrials, updateEthicsApproval, api } from '../api'
import DashboardLayout from './layout'

function IECDecisionPanel({ onUpdated }) {
  const [trial, setTrial] = useState(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Form states
  const [status, setStatus] = useState('approved')
  const [approvalNumber, setApprovalNumber] = useState('')
  const [approvalDate, setApprovalDate] = useState('')
  const [validUntil, setValidUntil] = useState('')
  const [notes, setNotes] = useState('')
  const [saeCount, setSaeCount] = useState(0)
  const [sirenResolved, setSirenResolved] = useState(false)

  useEffect(() => {
    async function checkSafety() {
      try {
        const res = await api('/api/adverse-events?serious_only=true&limit=100')
        if (res.items && res.items.length > 0) {
          setSaeCount(res.items.length)
        }
      } catch (err) {
        console.error("Failed to check safety signals", err)
      }
    }
    checkSafety()
  }, [])

  async function quickAction(newStatus) {
    if (!trial) return
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const payload = {
        ethics_approval_status: newStatus,
        ethics_approval_number: trial.ethics_approval_number || `IEC/AIIA/2026/${String(trial.id).padStart(3, '0')}`,
        ethics_approval_date: trial.ethics_approval_date || new Date().toISOString().slice(0, 10),
        ethics_approval_valid_until: trial.ethics_approval_valid_until || '2027-12-31'
      }
      await updateEthicsApproval(trial.id, payload)
      setSuccess(`Trial successfully ${newStatus.toUpperCase()}!`)
      setSirenResolved(true)
      await loadTrial()
      if (onUpdated) onUpdated()
    } catch (err) {
      setError(err?.message || `Failed to ${newStatus} trial`)
    } finally {
      setSaving(false)
    }
  }


  async function loadTrial() {
    setLoading(true)
    setError('')
    try {
      const res = await fetchTrials()
      const current = res.items?.[0]
      if (current) {
        setTrial(current)
        setStatus(current.ethics_approval_status || 'approved')
        setApprovalNumber(current.ethics_approval_number || `IEC/AIIA/2026/${String(current.id).padStart(3, '0')}`)
        setApprovalDate(current.ethics_approval_date || new Date().toISOString().slice(0, 10))
        if (current.ethics_approval_valid_until) {
          setValidUntil(current.ethics_approval_valid_until)
        } else {
          const nextYear = new Date()
          nextYear.setFullYear(nextYear.getFullYear() + 1)
          setValidUntil(nextYear.toISOString().slice(0, 10))
        }
      }
    } catch (err) {
      setError(err?.message || 'Failed to load trial protocol')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTrial()
  }, [])

  async function handleDecisionSubmit(e) {
    e.preventDefault()
    if (!trial) return
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const payload = {
        ethics_approval_status: status,
        ethics_approval_number: status === 'approved' || status === 'expired' ? approvalNumber.trim() : null,
        ethics_approval_date: status === 'approved' || status === 'expired' ? approvalDate : null,
        ethics_approval_valid_until: status === 'approved' || status === 'expired' ? validUntil : null,
      }

      await updateEthicsApproval(trial.id, payload)
      setSuccess(`IEC Decision successfully recorded and broadcast! Status is now ${status.toUpperCase()}.`)
      await loadTrial()
      if (onUpdated) onUpdated()
    } catch (err) {
      setError(err?.message || 'Failed to submit IEC decision')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="rounded-xl border border-indigo-200 bg-white p-5 shadow-sm lg:col-span-2">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-slate-900">
              Institutional Ethics Committee (IEC) Oversight & Approval
            </h3>
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold uppercase tracking-wider ${
              trial?.ethics_approval_status === 'approved' ? 'bg-emerald-100 text-emerald-800' :
              trial?.ethics_approval_status === 'pending_ethics' ? 'bg-amber-100 text-amber-800' :
              'bg-red-100 text-red-800'
            }`}>
              {trial?.ethics_approval_status || 'Checking...'}
            </span>
          </div>
          <p className="mt-0.5 text-xs text-slate-500">
            NDCT Rules 2019 Rule 22: Clinical screening and enrollment are physically blocked by software unless active IEC approval is on record.
          </p>
        </div>
      </div>

      {error && (
        <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-2.5 text-xs text-red-700">
          <strong>Error:</strong> {error}
        </div>
      )}

      {success && (
        <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 p-2.5 text-xs text-emerald-700">
          <strong>Success:</strong> {success}
        </div>
      )}

      
      {saeCount > 0 && !sirenResolved && (
        <div className="mt-4 mb-6 flex flex-col sm:flex-row items-center justify-between rounded-xl border-2 border-red-500 bg-red-100 p-4 shadow-sm animate-pulse">
          <div className="flex items-center gap-3 mb-4 sm:mb-0">
            <span className="text-4xl">🚨</span>
            <div>
              <h2 className="text-lg font-bold text-red-700 uppercase tracking-wider">
                Critical Alert: {saeCount} Serious Adverse Event(s)
              </h2>
              <p className="text-sm font-medium text-red-600">
                Severe safety signals detected. Immediate Ethics Committee ruling required.
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => quickAction('approved')}
              disabled={saving}
              className="rounded-lg border-2 border-emerald-600 bg-emerald-50 px-4 py-2 text-sm font-bold text-emerald-700 hover:bg-emerald-600 hover:text-white transition-colors"
            >
              ✅ Accept (Clear)
            </button>
            <button
              onClick={() => quickAction('rejected')}
              disabled={saving}
              className="rounded-lg bg-red-600 px-4 py-2 text-sm font-bold text-white shadow hover:bg-red-700 transition-colors"
            >
              ❌ Reject (Halt Trial)
            </button>
          </div>
        </div>
      )}

      <form onSubmit={handleDecisionSubmit} className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label className="block text-xs font-medium text-slate-700">Committee Decision</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-900 focus:border-aiia-500 focus:outline-none"
          >
            <option value="approved">Approved (Clear for Recruitment)</option>
            <option value="pending">Pending Review (Block Enrollment)</option>
            <option value="rejected">Rejected (Halt Trial)</option>
            <option value="expired">Expired (Requires Renewal)</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-700">IEC Approval Reference Number</label>
          <input
            type="text"
            required={status === 'approved' || status === 'expired'}
            disabled={status !== 'approved' && status !== 'expired'}
            value={approvalNumber}
            onChange={(e) => setApprovalNumber(e.target.value)}
            placeholder="e.g. IEC/AIIA/2026/042"
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:border-aiia-500 focus:outline-none disabled:bg-slate-100"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-700">Approval Effective Date</label>
          <input
            type="date"
            required={status === 'approved' || status === 'expired'}
            disabled={status !== 'approved' && status !== 'expired'}
            value={approvalDate}
            onChange={(e) => setApprovalDate(e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-900 focus:border-aiia-500 focus:outline-none disabled:bg-slate-100"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-700">Valid Until Date</label>
          <input
            type="date"
            required={status === 'approved' || status === 'expired'}
            disabled={status !== 'approved' && status !== 'expired'}
            value={validUntil}
            onChange={(e) => setValidUntil(e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-900 focus:border-aiia-500 focus:outline-none disabled:bg-slate-100"
          />
        </div>

        <div className="sm:col-span-2 lg:col-span-4 flex items-center justify-between pt-2">
          <div className="text-xs text-slate-500">
            Current Protocol: <strong className="text-slate-800">{trial?.protocol_number || 'AIIA-ASH-2026-01'}</strong>
          </div>
          <button
            type="submit"
            disabled={saving || loading}
            className="rounded-lg bg-aiia-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-aiia-700 focus:outline-none disabled:opacity-50 transition-colors"
          >
            {saving ? 'Submitting IEC Decision...' : 'Record & Broadcast IEC Decision'}
          </button>
        </div>
      </form>
    </section>
  )
}







export default function Ethics(props) {
  return (
    <div className="space-y-6">
      
      <div className="flex items-center justify-between rounded-lg border border-purple-100 bg-purple-50/70 px-4 py-2.5 text-xs text-purple-900">
        <span className="flex items-center gap-2 font-medium">
          <span className="flex h-2 w-2 rounded-full bg-purple-600"></span>
          🔒 DPDP Act 2023: De-identified Independent Ethics Oversight Mode
        </span>
        <span className="text-purple-700 hidden sm:inline">
          Access is strictly restricted to safety pharmacovigilance and protocol compliance.
        </span>
      </div>

      <IECDecisionPanel />

      <DashboardLayout
        {...props}
        wide={['sae_reporting', 'deviations']}
        note="Severity is how bad an event felt; seriousness is a regulatory category - death, hospitalisation, disability - that starts a reporting clock. A severe headache is not serious. Only the serious ones are listed below."
      />
    </div>
  )
}
