import { useEffect, useState } from 'react'
import { fetchSponsorSaeQueue, submitSaeToEc, simulateOverdueSae } from '../api'

export default function SaeRegulatoryClockQueue() {
  const [saes, setSaes] = useState([])
  const [loading, setLoading] = useState(true)
  const [submittingId, setSubmittingId] = useState(null)
  const [simulating, setSimulating] = useState(false)
  const [actionNotice, setActionNotice] = useState(null)

  const reload = () => {
    fetchSponsorSaeQueue()
      .then((data) => {
        setSaes(data || [])
      })
      .catch((err) => {
        console.error('Failed to load SAE queue:', err)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    reload()
  }, [])

  const handleSubmit = async (eventId) => {
    setSubmittingId(eventId)
    try {
      await submitSaeToEc(eventId)
      setActionNotice('SAE report formally transmitted to Institutional Ethics Committee!')
      setTimeout(() => setActionNotice(null), 4000)
      reload()
    } catch (err) {
      alert(err.detail || err.message || 'Failed to submit SAE to Ethics Committee')
    } finally {
      setSubmittingId(null)
    }
  }

  const handleSimulateOverdue = async () => {
    setSimulating(true)
    try {
      await simulateOverdueSae()
      setActionNotice('🚨 Simulated Overdue SAE generated! Elapsed clock > 24h statutory window.')
      setTimeout(() => setActionNotice(null), 5000)
      reload()
    } catch (err) {
      alert(err.detail || err.message || 'Failed to generate simulated overdue SAE')
    } finally {
      setSimulating(false)
    }
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 text-xs text-slate-500">
        Loading statutory SAE reporting clock queue...
      </div>
    )
  }

  const overdueCount = saes.filter((s) => s.clock_status === 'OVERDUE').length
  const dueSoonCount = saes.filter((s) => s.clock_status === 'DUE_SOON').length

  return (
    <section className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {actionNotice && (
        <div className="bg-emerald-50 border-b border-emerald-200 px-5 py-2 text-xs font-semibold text-emerald-900 flex items-center justify-between">
          <span>✓ {actionNotice}</span>
          <button onClick={() => setActionNotice(null)} className="text-emerald-700 hover:text-emerald-900 font-bold">✕</button>
        </div>
      )}
      <div className="border-b border-slate-100 bg-slate-50/70 px-5 py-3.5 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-base">🚨</span>
          <div>
            <h2 className="text-sm font-semibold text-slate-900">
              Open Serious Adverse Events (SAE) & Statutory 24-Hour Reporting Clocks
            </h2>
            <p className="text-[11px] text-slate-500">
              NDCT Rules 2019 Rule 42 & GCP-ASU statutory reporting timeline oversight.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={simulating}
            onClick={handleSimulateOverdue}
            className="inline-flex items-center gap-1 rounded border border-rose-300 bg-rose-50 hover:bg-rose-100 text-rose-800 px-2.5 py-1 text-xs font-semibold shadow-xs transition disabled:opacity-50"
            title="NDCT Rules 2019 Rule 42 compliance demonstration: inject an SAE with >24h elapsed reporting clock"
          >
            <span>⚡</span>
            <span>{simulating ? 'Generating…' : 'Simulate Overdue 24h Clock (Demo)'}</span>
          </button>
          {overdueCount > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 border border-rose-200 px-2.5 py-0.5 text-xs font-semibold text-rose-800 animate-pulse">
              <span>⚠️</span>
              <span>{overdueCount} Overdue Clock{overdueCount > 1 ? 's' : ''}</span>
            </span>
          )}
          {dueSoonCount > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 border border-amber-200 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
              <span>⏱️</span>
              <span>{dueSoonCount} Due Soon (&lt;6h)</span>
            </span>
          )}
          <span className="text-xs text-slate-500 font-mono">
            {saes.length} total SAE{saes.length === 1 ? '' : 's'} recorded
          </span>
        </div>
      </div>

      {saes.length === 0 ? (
        <div className="p-6 text-center text-xs text-slate-500">
          ✅ No Serious Adverse Events reported across active study sites. All safety reporting clocks compliant.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-[11px] font-semibold text-slate-600 uppercase tracking-wider">
                <th className="px-4 py-2.5">Event ID</th>
                <th className="px-4 py-2.5">Participant</th>
                <th className="px-4 py-2.5">Site / Institute</th>
                <th className="px-4 py-2.5">Verbatim Term</th>
                <th className="px-4 py-2.5">Seriousness Criterion</th>
                <th className="px-4 py-2.5">Onset Date</th>
                <th className="px-4 py-2.5">24h Statutory Clock</th>
                <th className="px-4 py-2.5">EC Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {saes.map((ae) => {
                const isOverdue = ae.clock_status === 'OVERDUE'
                const isDueSoon = ae.clock_status === 'DUE_SOON'
                const isReported = ae.clock_status === 'REPORTED_TO_EC'

                return (
                  <tr
                    key={ae.id}
                    className={`hover:bg-slate-50/70 transition-colors ${
                      isOverdue ? 'bg-rose-50/40' : isDueSoon ? 'bg-amber-50/30' : ''
                    }`}
                  >
                    <td className="px-4 py-3 font-mono font-medium text-slate-900 whitespace-nowrap">
                      {ae.ae_number}
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-700 whitespace-nowrap">
                      {ae.subject_code}
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      <span className="font-mono text-[11px] text-slate-500 mr-1">[{ae.site_code}]</span>
                      {ae.site_name}
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-900">
                      {ae.term_verbatim}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {ae.seriousness_criteria}
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-600 whitespace-nowrap">
                      {ae.onset_date}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                          isOverdue
                            ? 'bg-rose-100 text-rose-800 border border-rose-300'
                            : isDueSoon
                            ? 'bg-amber-100 text-amber-800 border border-amber-300'
                            : isReported
                            ? 'bg-slate-100 text-slate-700 border border-slate-200'
                            : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                        }`}
                      >
                        <span
                          className={`h-1.5 w-1.5 rounded-full ${
                            isOverdue
                              ? 'bg-rose-600 animate-ping'
                              : isDueSoon
                              ? 'bg-amber-600'
                              : isReported
                              ? 'bg-slate-400'
                              : 'bg-emerald-600'
                          }`}
                        />
                        {ae.clock_label}
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {ae.ec_decision ? (
                        <div className="flex flex-col items-start">
                          <span className={`inline-flex items-center gap-1 font-bold text-[11px] ${
                            ae.ec_decision === 'accepted'
                              ? 'text-emerald-700'
                              : ae.ec_decision === 'rejected'
                              ? 'text-rose-700'
                              : 'text-amber-700'
                          }`}>
                            <span>{ae.ec_decision === 'accepted' ? '✅' : '⚖️'}</span>
                            <span>IEC: {ae.ec_decision.toUpperCase()}</span>
                          </span>
                          <span className="text-[10px] text-slate-400 font-mono">
                            {ae.ec_decision_date || ae.reported_to_ec_date}
                          </span>
                        </div>
                      ) : ae.reported_to_ec ? (
                        <div className="flex flex-col items-start">
                          <span className="inline-flex items-center text-emerald-700 font-semibold text-[11px]">
                            ✓ Submitted to IEC
                          </span>
                          {ae.reported_to_ec_date && (
                            <span className="text-[10px] text-slate-400 font-mono">
                              {ae.reported_to_ec_date}
                            </span>
                          )}
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <span className="inline-flex items-center text-rose-700 font-medium text-[11px]">
                            Pending Submission
                          </span>
                          <button
                            type="button"
                            disabled={submittingId === ae.id}
                            onClick={() => handleSubmit(ae.id)}
                            className="inline-flex items-center rounded border border-rose-300 bg-white hover:bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-800 transition shadow-xs cursor-pointer"
                            title="Formally transmit SAE notification to Institutional Ethics Committee"
                          >
                            {submittingId === ae.id ? 'Submitting…' : '✉️ Submit to IEC'}
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
