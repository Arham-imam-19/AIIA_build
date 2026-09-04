import { useEffect, useState } from 'react'
import { fetchSponsorMilestones } from '../api'
import RegisterCtriModal from './RegisterCtriModal'

export default function RegulatoryMilestonesPanel({ consentPct }) {
  const [milestones, setMilestones] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCtriModal, setShowCtriModal] = useState(false)

  const reload = () => {
    fetchSponsorMilestones()
      .then((data) => setMilestones(data || []))
      .catch((err) => console.error('Failed to reload milestones:', err))
  }

  useEffect(() => {
    fetchSponsorMilestones()
      .then((data) => {
        setMilestones(data || [])
      })
      .catch((err) => {
        console.error('Failed to load milestones:', err)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 text-xs text-slate-500">
        Loading regulatory and ethics milestones...
      </div>
    )
  }

  if (!milestones.length) {
    return null
  }

  const primary = milestones[0]

  return (
    <section className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="border-b border-slate-100 bg-slate-50/70 px-5 py-3.5 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-base">⚖️</span>
          <div>
            <h2 className="text-sm font-semibold text-slate-900">
              Regulatory & Ethics Governance Milestones
            </h2>
            <p className="text-[11px] text-slate-500">
              Protocol: <span className="font-mono font-medium text-slate-700">{primary.protocol_number}</span> &bull; {primary.title}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
            Phase {primary.phase} &bull; {primary.status?.toUpperCase()}
          </span>
          {consentPct !== undefined && (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-xs font-medium text-emerald-800">
              <span>DPDP Consent:</span>
              <span className="font-bold">{consentPct}%</span>
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-slate-100 p-5 gap-4">
        {/* CTRI Registration Milestone */}
        <div className="flex flex-col justify-between space-y-2">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                CTRI Registration
              </span>
              <span className={`inline-flex items-center rounded px-2 py-0.5 text-[11px] font-semibold ${
                primary.ctri_tone === 'good'
                  ? 'bg-emerald-100 text-emerald-800'
                  : primary.ctri_tone === 'bad'
                  ? 'bg-rose-100 text-rose-800 animate-pulse'
                  : 'bg-amber-100 text-amber-800'
              }`}>
                {primary.ctri_status}
              </span>
            </div>
            <div className="mt-2 text-sm font-mono font-medium text-slate-900">
              {primary.ctri_number}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">
              Registered: {primary.ctri_date || 'Pending formal registry approval'}
            </div>
            <button
              type="button"
              onClick={() => setShowCtriModal(true)}
              className="mt-2 inline-flex items-center gap-1 border border-slate-300 bg-white hover:bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-800 shadow-sm transition"
            >
              <span>📝</span>
              <span>{primary.ctri_status === 'REGISTERED' ? 'Edit CTRI Registration' : 'Register Prospective CTRI Number'}</span>
            </button>
          </div>
          <div className="text-[11px] text-slate-500 bg-slate-50 rounded p-2 border border-slate-100">
            NDCT Rules 2019 Rule 22: Mandatory prospective registration prior to participant screening.
          </div>
        </div>

        {/* Ethics Committee Approval & Renewal Milestone */}
        <div className="flex flex-col justify-between space-y-2">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                IEC Approval Status
              </span>
              <span className={`inline-flex items-center rounded px-2 py-0.5 text-[11px] font-semibold ${
                primary.ec_tone === 'good'
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-rose-100 text-rose-800'
              }`}>
                {primary.ec_status}
              </span>
            </div>
            <div className="mt-2 text-sm font-mono font-medium text-slate-900">
              {primary.ec_number}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">
              Approval Date: {primary.ec_approval_date || 'Pending'}
            </div>
          </div>
          <div className={`rounded p-2 border text-[11px] ${
            primary.renewal_tone === 'bad'
              ? 'bg-rose-50 border-rose-200 text-rose-800'
              : primary.renewal_tone === 'warn'
              ? 'bg-amber-50 border-amber-200 text-amber-800'
              : 'bg-emerald-50 border-emerald-200 text-emerald-800'
          }`}>
            <span className="font-semibold">Next Annual Renewal:</span> {primary.renewal_status}
            <div className="text-[10px] mt-0.5 opacity-80">
              Valid Until: {primary.ec_valid_until}
            </div>
          </div>
        </div>

        {/* CDSCO Regulatory Clearance Milestone */}
        <div className="flex flex-col justify-between space-y-2">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                Regulatory Clearance
              </span>
              <span className="inline-flex items-center rounded px-2 py-0.5 text-[11px] font-semibold bg-blue-100 text-blue-800">
                AUTHORIZED
              </span>
            </div>
            <div className="mt-2 text-sm font-mono font-medium text-slate-900 truncate">
              {primary.regulatory_number}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">
              Authorization Date: {primary.regulatory_date || 'Active under Ayush GCP Guidelines'}
            </div>
          </div>
          <div className="text-[11px] text-slate-500 bg-slate-50 rounded p-2 border border-slate-100">
            Monitored under Schedule Y & New Drugs and Clinical Trials Rules 2019 GCP standards.
          </div>
        </div>
      </div>

      {showCtriModal && (
        <RegisterCtriModal
          trial={{
            id: primary.trial_id,
            protocol_number: primary.protocol_number,
            title: primary.title,
            short_title: primary.title,
            ctri_number: primary.ctri_number === 'Not Registered' ? '' : primary.ctri_number,
            ctri_registration_date: primary.ctri_date,
          }}
          onClose={() => setShowCtriModal(false)}
          onSuccess={() => {
            reload()
            setShowCtriModal(false)
          }}
        />
      )}
    </section>
  )
}
