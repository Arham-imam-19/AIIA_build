import React, { useEffect, useState } from 'react'
import { fetchSubjects, fetchSites, fetchTrials } from '../api'
import { useAuth } from '../auth'

export default function ParticipantsListPage({ onSelectPatient, onNavigateScreenParticipant }) {
  const { user } = useAuth()

  const [subjects, setSubjects] = useState([])
  const [trials, setTrials] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [site, setSite] = useState(null)
  const [trial, setTrial] = useState(null)

  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [protocolFilter, setProtocolFilter] = useState('all')

  useEffect(() => {
    let isMounted = true
    setLoading(true)

    Promise.all([
      fetchSubjects({ limit: 200 }),
      fetchSites(),
      fetchTrials(),
    ])
      .then(([subRes, siteRes, trialRes]) => {
        if (!isMounted) return
        setSubjects(subRes.items || [])
        const trialList = trialRes.items || []
        setTrials(trialList)
        const userSite = siteRes.items?.find((s) => s.id === user?.site_id) || siteRes.items?.[0]
        setSite(userSite)
        setTrial(trialList[0] || null)
        setLoading(false)
      })
      .catch((err) => {
        if (!isMounted) return
        setError(err.detail || err.message || 'Failed to load participants.')
        setLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [user])

  const trialMap = Object.fromEntries(trials.map((t) => [t.id, t]))

  const filteredSubjects = subjects.filter((s) => {
    const matchesSearch =
      !searchTerm ||
      s.subject_code.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (s.prakriti && s.prakriti.toLowerCase().includes(searchTerm.toLowerCase()))
    const matchesStatus =
      statusFilter === 'all' || s.status === statusFilter
    const matchesProtocol =
      protocolFilter === 'all' || String(s.trial_id) === String(protocolFilter)
    return matchesSearch && matchesStatus && matchesProtocol
  })

  // Summary tallies
  const totalCount = subjects.length
  const screeningCount = subjects.filter((s) => s.status === 'screening').length
  const enrolledCount = subjects.filter((s) => s.status === 'enrolled' || s.status === 'active').length
  const completedCount = subjects.filter((s) => s.status === 'completed').length
  const failedCount = subjects.filter((s) => s.status === 'screen_failed').length

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="border border-slate-300 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="border border-slate-300 bg-slate-100 px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-slate-700">
                Registry Module
              </span>
              <span className="font-mono text-xs font-semibold text-slate-500">
                Scope: Site {site?.id ?? user?.site_id ?? '01'} &middot; {site?.site_name || 'All India Institute of Ayurveda'}
              </span>
            </div>
            <h1 className="mt-1 text-xl font-bold tracking-tight text-slate-900 uppercase">
              Study Participants Directory & Progress Logs
            </h1>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={onNavigateScreenParticipant}
              className="border border-blue-900 bg-blue-900 px-4 py-2 text-xs font-bold uppercase tracking-wider text-white hover:bg-blue-800 transition shadow-sm"
            >
              + Screen New Participant
            </button>
          </div>
        </div>

        {/* Server-Side Access Control Notice */}
        <div className="mt-3 flex items-start gap-2.5 border-l-4 border-slate-700 bg-slate-50 p-3 text-xs text-slate-700">
          <div className="font-bold text-slate-900 uppercase tracking-wider text-[11px] whitespace-nowrap">
            Multi-Protocol Registry:
          </div>
          <div className="leading-relaxed text-[11px]">
            As <strong>{user?.full_name}</strong> ({user?.role_label}), records are scoped across participating protocols under <strong>Site {site?.id ?? user?.site_id ?? '01'}</strong> ({site?.site_name || 'Institute'}). Cross-site patient inspection remains restricted by NDCT Rules 2019.
          </div>
        </div>
      </div>

      {/* Metric Counters */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
        <div className="border border-slate-300 bg-white p-3 shadow-sm">
          <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-500">Total Scoped</span>
          <span className="mt-1 block font-mono text-xl font-bold text-slate-900">{totalCount}</span>
        </div>
        <div className="border border-amber-300 bg-amber-50/50 p-3 shadow-sm">
          <span className="block text-[10px] font-bold uppercase tracking-wider text-amber-800">In Screening</span>
          <span className="mt-1 block font-mono text-xl font-bold text-amber-900">{screeningCount}</span>
        </div>
        <div className="border border-emerald-300 bg-emerald-50/50 p-3 shadow-sm">
          <span className="block text-[10px] font-bold uppercase tracking-wider text-emerald-800">Enrolled / Active</span>
          <span className="mt-1 block font-mono text-xl font-bold text-emerald-900">{enrolledCount}</span>
        </div>
        <div className="border border-blue-300 bg-blue-50/50 p-3 shadow-sm">
          <span className="block text-[10px] font-bold uppercase tracking-wider text-blue-800">Completed</span>
          <span className="mt-1 block font-mono text-xl font-bold text-blue-900">{completedCount}</span>
        </div>
        <div className="border border-red-300 bg-red-50/50 p-3 shadow-sm">
          <span className="block text-[10px] font-bold uppercase tracking-wider text-red-800">Screen Failures</span>
          <span className="mt-1 block font-mono text-xl font-bold text-red-900">{failedCount}</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="border border-slate-300 bg-white p-4 shadow-sm flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">Search Subject / Prakriti</label>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="e.g. AIIA-ASH-01-081"
              className="border border-slate-300 p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none w-48"
            />
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">Target Protocol</label>
            <select
              value={protocolFilter}
              onChange={(e) => setProtocolFilter(e.target.value)}
              className="border border-slate-300 p-2 text-xs font-semibold text-slate-900 focus:border-slate-800 focus:outline-none"
            >
              <option value="all">All Protocols ({trials.length})</option>
              {trials.map((t) => (
                <option key={t.id} value={t.id}>
                  [{t.protocol_number}] {t.title?.slice(0, 26)}...
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">Status Filter</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="border border-slate-300 p-2 text-xs font-medium text-slate-900 focus:border-slate-800 focus:outline-none"
            >
              <option value="all">All Lifecycle States</option>
              <option value="screening">Screening</option>
              <option value="enrolled">Enrolled</option>
              <option value="active">Active Treatment</option>
              <option value="completed">Completed</option>
              <option value="screen_failed">Screen Failed</option>
              <option value="withdrawn">Withdrawn</option>
            </select>
          </div>
        </div>

        <div className="text-[11px] text-slate-500 font-mono">
          Showing <strong>{filteredSubjects.length}</strong> of <strong>{subjects.length}</strong> registered participants
        </div>
      </div>

      {/* Participants Table */}
      <div className="border border-slate-300 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-xs text-slate-500">
            Loading scoped participant records from clinical ledger...
          </div>
        ) : error ? (
          <div className="p-6 text-xs text-red-700 bg-red-50 border-b border-red-200">
            <strong>Error:</strong> {error}
          </div>
        ) : filteredSubjects.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500">
            No participant records found matching the specified search criteria.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b-2 border-slate-800 bg-slate-100 font-bold uppercase text-[10px] tracking-wider text-slate-700">
                  <th className="p-3 border-r border-slate-200">Subject Code</th>
                  <th className="p-3 border-r border-slate-200">Protocol / Trial</th>
                  <th className="p-3 border-r border-slate-200">Status</th>
                  <th className="p-3 border-r border-slate-200">Study Arm</th>
                  <th className="p-3 border-r border-slate-200">Demographics</th>
                  <th className="p-3 border-r border-slate-200">Ayurvedic Prakriti</th>
                  <th className="p-3 border-r border-slate-200">Screening Date</th>
                  <th className="p-3 text-right">Clinical Progress Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {filteredSubjects.map((s) => {
                  const statusColors = {
                    screening: 'bg-amber-50 text-amber-800 border-amber-300',
                    enrolled: 'bg-blue-50 text-blue-800 border-blue-300',
                    active: 'bg-emerald-50 text-emerald-800 border-emerald-300',
                    completed: 'bg-slate-100 text-slate-800 border-slate-300',
                    screen_failed: 'bg-red-50 text-red-800 border-red-300',
                    withdrawn: 'bg-purple-50 text-purple-800 border-purple-300',
                  }

                  const badgeClass = statusColors[s.status] || 'bg-slate-50 text-slate-700 border-slate-300'
                  const protocolInfo = trialMap[s.trial_id]

                  return (
                    <tr
                      key={s.id}
                      className="hover:bg-slate-50/80 transition cursor-pointer"
                      onClick={() => onSelectPatient(s.id)}
                    >
                      <td className="p-3 font-mono font-bold text-slate-900 border-r border-slate-200">
                        {s.subject_code}
                      </td>
                      <td className="p-3 border-r border-slate-200">
                        <div className="font-mono text-[11px] font-bold text-slate-900 flex items-center gap-1.5">
                          <span className="inline-block h-2 w-2 rounded-full bg-aiia-600"></span>
                          {protocolInfo?.protocol_number || s.protocol_version || `Trial #${s.trial_id}`}
                        </div>
                        <div className="text-[10px] text-slate-500 truncate max-w-[160px]" title={protocolInfo?.title}>
                          {protocolInfo?.title || 'Clinical Protocol'}
                        </div>
                      </td>
                      <td className="p-3 border-r border-slate-200">
                        <span className={`inline-block border px-2 py-0.5 font-mono text-[10px] font-bold uppercase ${badgeClass}`}>
                          {s.status}
                        </span>
                      </td>
                      <td className="p-3 font-medium text-slate-800 border-r border-slate-200">
                        {s.arm === 'not_randomized' ? (
                          <span className="text-slate-400 font-mono text-[11px]">Not Randomized</span>
                        ) : (
                          <span className="font-semibold text-slate-900 uppercase text-[11px]">{s.arm}</span>
                        )}
                      </td>
                      <td className="p-3 text-slate-700 border-r border-slate-200">
                        <span className="capitalize">{s.sex}</span>
                        {s.year_of_birth && (
                          <span className="text-slate-500 ml-1">
                            ({new Date().getFullYear() - s.year_of_birth} yrs)
                          </span>
                        )}
                      </td>
                      <td className="p-3 border-r border-slate-200 font-mono text-slate-800 uppercase text-[11px]">
                        {s.prakriti ? s.prakriti.replace('_', '-') : '—'}
                      </td>
                      <td className="p-3 font-mono text-slate-600 border-r border-slate-200 text-[11px]">
                        {s.screening_date || '—'}
                      </td>
                      <td className="p-3 text-right">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            onSelectPatient(s.id)
                          }}
                          className="border border-slate-900 bg-slate-900 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-white hover:bg-slate-800 transition"
                        >
                          Detail & Log &rarr;
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
