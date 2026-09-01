import { useEffect, useState } from 'react'
import { fetchSubjectDossier, fetchSubjectFhirBundle } from '../api'

export default function ParticipantDossierModal({ subjectId, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('timeline') // 'timeline' | 'visits' | 'safety' | 'fhir'
  const [fhirJson, setFhirJson] = useState(null)

  useEffect(() => {
    if (!subjectId) return
    setLoading(true)
    setError(null)
    fetchSubjectDossier(subjectId)
      .then((res) => {
        setData(res)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.detail || err.message)
        setLoading(false)
      })
  }, [subjectId])

  async function handleLoadFhir() {
    try {
      const fhir = await fetchSubjectFhirBundle(subjectId)
      setFhirJson(fhir)
      setActiveTab('fhir')
    } catch (err) {
      setError(`Failed to load FHIR bundle: ${err.message}`)
    }
  }

  if (!subjectId) return null

  const profile = data?.profile
  const timeline = data?.timeline || []
  const visits = data?.visits || []
  const adverseEvents = data?.adverse_events || []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="flex h-[90vh] w-full max-w-5xl flex-col rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/70 px-6 py-4 dark:border-slate-800 dark:bg-slate-800/50">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-aiia-100 text-aiia-700 font-bold text-base dark:bg-aiia-950 dark:text-aiia-300">
              📋
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  Participant Dossier: {profile?.subject_code || `Subject #${subjectId}`}
                </h3>
                {profile?.status && (
                  <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 uppercase">
                    {profile.status}
                  </span>
                )}
                {profile?.is_dpdp_masked && (
                  <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-800 dark:bg-blue-950 dark:text-blue-300">
                    🔒 DPDP Minimization Active
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                {profile?.site_name} ({profile?.site_code}) • Protocol {profile?.protocol_number}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleLoadFhir}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              🔥 View FHIR R4 Record
            </button>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Content Body */}
        {loading ? (
          <div className="flex flex-1 items-center justify-center p-12 text-sm text-slate-500">
            Loading comprehensive participant dossier & audit history...
          </div>
        ) : error ? (
          <div className="flex flex-1 items-center justify-center p-12 text-sm text-red-600">
            Error: {error}
          </div>
        ) : (
          <div className="flex flex-1 flex-col overflow-hidden">
            {/* Participant Demographics & Baseline Overview Card */}
            <div className="border-b border-slate-100 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6 text-xs">
                <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-slate-800/60">
                  <span className="text-slate-400 block text-[10px] uppercase font-semibold">Biological Sex & Age</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200 mt-0.5 block">
                    {profile?.sex?.toUpperCase()} • {profile?.age ? `${profile.age} yrs` : 'N/A'}
                  </span>
                </div>
                <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-slate-800/60">
                  <span className="text-slate-400 block text-[10px] uppercase font-semibold">Height / Weight / BMI</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200 mt-0.5 block">
                    {profile?.height_cm || '-'} cm / {profile?.weight_kg || '-'} kg ({profile?.bmi ? `${profile.bmi} kg/m²` : '-'})
                  </span>
                </div>
                <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-slate-800/60">
                  <span className="text-slate-400 block text-[10px] uppercase font-semibold">Ayurveda Prakriti</span>
                  <span className="font-bold text-amber-700 dark:text-amber-400 mt-0.5 block">
                    {profile?.prakriti?.toUpperCase() || 'UNASSESSED'}
                  </span>
                </div>
                <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-slate-800/60">
                  <span className="text-slate-400 block text-[10px] uppercase font-semibold">Randomized Arm</span>
                  <span className="font-bold text-indigo-700 dark:text-indigo-400 mt-0.5 block truncate" title={profile?.arm}>
                    {profile?.arm || 'Not Randomized'}
                  </span>
                </div>
                <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-slate-800/60">
                  <span className="text-slate-400 block text-[10px] uppercase font-semibold">Screening Date</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200 mt-0.5 block">
                    {profile?.screening_date || 'N/A'}
                  </span>
                </div>
                <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-slate-800/60">
                  <span className="text-slate-400 block text-[10px] uppercase font-semibold">E-Consent & ABHA</span>
                  <span className="font-bold text-emerald-700 dark:text-emerald-400 mt-0.5 block truncate">
                    {profile?.consent ? `✅ ${profile.consent.language.toUpperCase()} (${profile.consent.abha_id || 'ABHA Verified'})` : 'Pending'}
                  </span>
                </div>
              </div>
            </div>

            {/* Navigation Tabs */}
            <div className="flex border-b border-slate-200 bg-slate-50/50 px-6 dark:border-slate-800 dark:bg-slate-900/50">
              <button
                onClick={() => setActiveTab('timeline')}
                className={`border-b-2 py-3 px-4 text-xs font-semibold transition ${
                  activeTab === 'timeline'
                    ? 'border-aiia-600 text-aiia-700 dark:text-aiia-300'
                    : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400'
                }`}
              >
                🕒 Patient Chronological Audit Log ({timeline.length})
              </button>
              <button
                onClick={() => setActiveTab('visits')}
                className={`border-b-2 py-3 px-4 text-xs font-semibold transition ${
                  activeTab === 'visits'
                    ? 'border-aiia-600 text-aiia-700 dark:text-aiia-300'
                    : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400'
                }`}
              >
                🗓️ Protocol Study Visits ({visits.length})
              </button>
              <button
                onClick={() => setActiveTab('safety')}
                className={`border-b-2 py-3 px-4 text-xs font-semibold transition ${
                  activeTab === 'safety'
                    ? 'border-aiia-600 text-aiia-700 dark:text-aiia-300'
                    : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400'
                }`}
              >
                🚨 Adverse Events & Safety ({adverseEvents.length})
              </button>
              {fhirJson && (
                <button
                  onClick={() => setActiveTab('fhir')}
                  className={`border-b-2 py-3 px-4 text-xs font-semibold transition ${
                    activeTab === 'fhir'
                      ? 'border-aiia-600 text-aiia-700 dark:text-aiia-300'
                      : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400'
                  }`}
                >
                  🔥 HL7 FHIR R4 Bundle
                </button>
              )}
            </div>

            {/* Tab Views */}
            <div className="flex-1 overflow-y-auto p-6">
              {activeTab === 'timeline' && (
                <div className="relative border-l-2 border-slate-200 ml-4 space-y-6 dark:border-slate-800">
                  {timeline.map((evt) => {
                    const badgeColors = {
                      success: 'bg-emerald-500 ring-emerald-100',
                      danger: 'bg-red-500 ring-red-100',
                      warning: 'bg-amber-500 ring-amber-100',
                      info: 'bg-blue-500 ring-blue-100',
                    }
                    return (
                      <div key={evt.id} className="relative pl-6">
                        <span
                          className={`absolute -left-[9px] top-1.5 h-4 w-4 rounded-full ring-4 ${
                            badgeColors[evt.badge] || 'bg-slate-400 ring-slate-100'
                          }`}
                        />
                        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-800/70">
                          <div className="flex flex-wrap items-center justify-between gap-1">
                            <h4 className="text-xs font-bold text-slate-900 dark:text-white">
                              {evt.title}
                            </h4>
                            <span className="font-mono text-[11px] text-slate-500">
                              {evt.timestamp ? new Date(evt.timestamp).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : '-'} IST
                            </span>
                          </div>
                          <div className="mt-1 text-[11px] text-slate-500">
                            Logged by: <span className="font-medium text-slate-700 dark:text-slate-300">{evt.actor}</span>
                          </div>

                          {/* Key Details Grid */}
                          {evt.details && (
                            <div className="mt-3 grid grid-cols-2 gap-2 rounded-lg bg-slate-50 p-2.5 text-xs sm:grid-cols-3 dark:bg-slate-900/60">
                              {Object.entries(evt.details).map(([key, val]) => (
                                <div key={key}>
                                  <span className="text-[10px] text-slate-400 block font-medium">{key}</span>
                                  <span className="font-semibold text-slate-800 dark:text-slate-200 break-words">
                                    {String(val)}
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}

              {activeTab === 'visits' && (
                <div className="space-y-3">
                  {visits.map((v) => (
                    <div
                      key={v.id}
                      className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-800/60"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-xs text-slate-900 dark:text-white">
                            Visit {v.visit_number}: {v.visit_name}
                          </span>
                          <span
                            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${
                              v.status === 'completed'
                                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                                : v.status === 'missed'
                                ? 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300'
                                : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                            }`}
                          >
                            {v.status}
                          </span>
                          {v.is_protocol_deviation && (
                            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                              ⚠️ Protocol Deviation
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-500 mt-1">
                          Scheduled: {v.scheduled_date || 'N/A'} • Actual: {v.actual_date || 'Pending'}
                        </p>
                        {v.deviation_description && (
                          <p className="text-xs text-amber-600 dark:text-amber-400 mt-1 italic">
                            Deviation Note: {v.deviation_description}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {activeTab === 'safety' && (
                <div className="space-y-3">
                  {adverseEvents.length === 0 ? (
                    <p className="text-xs text-slate-500 italic">No adverse events recorded for this participant.</p>
                  ) : (
                    adverseEvents.map((ae) => (
                      <div
                        key={ae.id}
                        className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-800/60"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-slate-900 dark:text-white">
                            {ae.ae_number}: {ae.term_verbatim}
                          </span>
                          <span
                            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                              ae.is_serious
                                ? 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300'
                                : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                            }`}
                          >
                            {ae.is_serious ? '🚨 SERIOUS (SAE)' : 'MILD / NON-SERIOUS'}
                          </span>
                        </div>
                        <div className="mt-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                          <div>
                            <span className="text-[10px] text-slate-400 block">Onset Date</span>
                            <span className="font-medium text-slate-800 dark:text-slate-200">{ae.onset_date}</span>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-400 block">Severity / Causality</span>
                            <span className="font-medium text-slate-800 dark:text-slate-200 uppercase">
                              {ae.severity} • {ae.causality}
                            </span>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-400 block">Clinical Outcome</span>
                            <span className="font-medium text-slate-800 dark:text-slate-200 uppercase">
                              {ae.outcome}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {activeTab === 'fhir' && fhirJson && (
                <div className="rounded-xl bg-slate-950 p-4 font-mono text-xs text-emerald-400 overflow-auto max-h-[50vh]">
                  <pre>{JSON.stringify(fhirJson, null, 2)}</pre>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
