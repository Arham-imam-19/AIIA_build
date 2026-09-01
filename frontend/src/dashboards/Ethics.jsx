import { useState } from 'react'
import DashboardLayout from './layout'
import { api } from '../api'

export default function Ethics(props) {
  const [error, setError] = useState(null)

  const handleApproval = async (status) => {
    try {
      await api('/api/trials/1/ethics-approval', {
        method: 'PATCH',
        body: {
          ethics_approval_status: status,
          ethics_approval_number: "IEC-2026-001",
          ethics_approval_date: new Date().toISOString().split('T')[0],
          ethics_approval_valid_until: "2027-12-31"
        }
      })
      alert(`Trial officially ${status}!`)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <div className="flex gap-4 mb-6">
        <div className="bg-red-600 text-white px-4 py-3 rounded-xl shadow-lg flex items-center gap-3 w-1/2 animate-pulse">
          <span className="text-2xl">🚨</span>
          <div>
            <div className="text-sm font-bold uppercase tracking-wider">Emergency SAE Inbox</div>
            <div className="text-xs">1 new severe adverse event requires immediate review.</div>
          </div>
        </div>
        <div className="bg-white border border-slate-200 px-4 py-3 rounded-xl shadow-sm flex items-center justify-between w-1/2">
          <div>
            <div className="text-sm font-bold uppercase tracking-wider text-slate-900">Protocol Approval Queue</div>
            <div className="text-xs text-slate-500">Trial AIIA-ASH-2026-01 is pending IEC approval.</div>
          </div>
          <div className="flex gap-2">
            <button onClick={() => handleApproval('rejected')} className="px-3 py-1 bg-red-100 text-red-700 text-xs font-bold rounded hover:bg-red-200">REJECT</button>
            <button onClick={() => handleApproval('approved')} className="px-3 py-1 bg-green-600 text-white text-xs font-bold rounded hover:bg-green-700">APPROVE</button>
          </div>
        </div>
      </div>
      {error && <div className="mb-4 text-red-600 text-sm">{error}</div>}

      <DashboardLayout
        {...props}
        wide={['sae_reporting', 'deviations']}
        note="Severity is how bad an event felt; seriousness is a regulatory category - death, hospitalisation, disability - that starts a reporting clock."
      />
    </div>
  )
}
