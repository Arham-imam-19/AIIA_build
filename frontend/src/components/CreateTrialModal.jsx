import { useState, useEffect } from 'react'
import { createTrial, fetchSites } from '../api'
import { useAuth } from '../auth'

export default function CreateTrialModal({ onClose, onSuccess }) {
  const { user } = useAuth()
  const [protocolNumber, setProtocolNumber] = useState('AIIA-NEO-2026-05')
  const [title, setTitle] = useState('')
  const [shortTitle, setShortTitle] = useState('')
  const [phase, setPhase] = useState('phase_2')
  const [indication, setIndication] = useState('')
  const [indicationAyurveda, setIndicationAyurveda] = useState('')
  const [intervention, setIntervention] = useState('')
  const [comparator, setComparator] = useState('')
  const [design, setDesign] = useState('Randomized, Double-Blind, Parallel-Group Trial')
  const [sponsorName, setSponsorName] = useState('All India Institute of Ayurveda (AIIA)')
  const [targetEnrollment, setTargetEnrollment] = useState(100)
  
  // Available participating institutions / hospitals
  const [availableInstitutions, setAvailableInstitutions] = useState([])
  const [selectedSiteIds, setSelectedSiteIds] = useState([])
  const [loadingSites, setLoadingSites] = useState(false)
  
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoadingSites(true)
    fetchSites()
      .then((res) => {
        const items = res.items || []
        // Deduplicate distinct hospital institutions by site_code / name
        const seen = new Set()
        const uniqueInstitutions = []
        for (const s of items) {
          if (!seen.has(s.site_code)) {
            seen.add(s.site_code)
            uniqueInstitutions.push(s)
          }
        }

        if (user?.site_scoped && user?.site_id) {
          // Site-scoped users can only create protocols under their own hospital site
          const ownSite = uniqueInstitutions.find((i) => i.id === user.site_id) || uniqueInstitutions[0]
          const list = ownSite ? [ownSite] : uniqueInstitutions
          setAvailableInstitutions(list)
          setSelectedSiteIds(list.map((i) => i.id))
        } else {
          setAvailableInstitutions(uniqueInstitutions)
          // Default: select the first institution or primary site
          setSelectedSiteIds(uniqueInstitutions.length > 0 ? [uniqueInstitutions[0].id] : [])
        }
      })
      .catch(() => {})
      .finally(() => setLoadingSites(false))
  }, [user])

  function toggleSite(siteId) {
    if (user?.site_scoped) return // Site-scoped users cannot toggle away from their site
    setSelectedSiteIds((prev) =>
      prev.includes(siteId) ? prev.filter((id) => id !== siteId) : [...prev, siteId]
    )
  }

  function selectAllSites() {
    if (user?.site_scoped) return
    setSelectedSiteIds(availableInstitutions.map((i) => i.id))
  }

  function clearAllSites() {
    if (user?.site_scoped) return
    setSelectedSiteIds([])
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (availableInstitutions.length > 0 && selectedSiteIds.length === 0) {
      setError('Please select at least one participating hospital institution / site for this protocol.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await createTrial({
        protocol_number: protocolNumber.trim().toUpperCase(),
        title: title.trim(),
        short_title: shortTitle.trim() || undefined,
        phase,
        indication: indication.trim(),
        indication_ayurveda: indicationAyurveda.trim() || undefined,
        intervention: intervention.trim(),
        comparator: comparator.trim() || undefined,
        design: design.trim(),
        sponsor_name: sponsorName.trim(),
        target_enrollment: Number(targetEnrollment),
        participating_site_ids: selectedSiteIds,
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4">
      <div className="w-full max-w-2xl border border-slate-400 bg-white p-6 shadow-2xl max-h-[92vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-200 pb-3">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Government of India &middot; Ministry of Ayush
            </div>
            <h3 className="text-sm font-bold uppercase tracking-wide text-slate-900 mt-0.5">
              Define &amp; Register Clinical Trial Protocol
            </h3>
            <p className="text-xs text-slate-600">
              ICH GCP E6(R2), CDISC TS Domain &amp; Indian CTRI Compliant Multi-Centric Setup
            </p>
          </div>
          <button
            onClick={onClose}
            className="border border-slate-300 bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700 hover:bg-slate-200"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="mt-3 border border-red-600 bg-red-50 p-3 text-xs font-medium text-red-900">
            {typeof error === 'string' ? error : JSON.stringify(error)}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-800">
                Protocol Number <span className="text-red-600">*</span>
              </label>
              <input
                type="text"
                required
                value={protocolNumber}
                onChange={(e) => setProtocolNumber(e.target.value)}
                placeholder="e.g. AIIA-ASH-2026-02"
                className="mt-1 w-full border border-slate-300 bg-white p-2 font-mono font-bold text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-800">
                Trial Phase <span className="text-red-600">*</span>
              </label>
              <select
                value={phase}
                onChange={(e) => setPhase(e.target.value)}
                className="mt-1 w-full border border-slate-300 bg-white p-2 text-xs font-medium text-slate-900 focus:border-slate-800 focus:outline-none"
              >
                <option value="phase_1">Phase I (Safety &amp; Pharmacokinetics)</option>
                <option value="phase_2">Phase II (Therapeutic Exploratory / Dose-Ranging)</option>
                <option value="phase_3">Phase III (Confirmatory Multi-Centric Efficacy)</option>
                <option value="phase_4">Phase IV (Post-Marketing Surveillance / Real-World)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-800">
              Full Scientific Study Title <span className="text-red-600">*</span>
            </label>
            <textarea
              required
              rows={2}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. A Multi-Centric, Randomized, Double-Blind Active-Controlled Clinical Trial Evaluating Efficacy and Safety of..."
              className="mt-1 w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-800">
                Biomedical Indication <span className="text-red-600">*</span>
              </label>
              <input
                type="text"
                required
                value={indication}
                onChange={(e) => setIndication(e.target.value)}
                placeholder="e.g. Type 2 Diabetes Mellitus"
                className="mt-1 w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-800">
                Ayurvedic Indication (NAMASTE / ICD-11 TM2)
              </label>
              <input
                type="text"
                value={indicationAyurveda}
                onChange={(e) => setIndicationAyurveda(e.target.value)}
                placeholder="e.g. Madhumeha / Prameha"
                className="mt-1 w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-800">
                Investigational Product (IP) / Formulation <span className="text-red-600">*</span>
              </label>
              <input
                type="text"
                required
                value={intervention}
                onChange={(e) => setIntervention(e.target.value)}
                placeholder="e.g. Nisha-Amalaki Ghanavati 500mg TID"
                className="mt-1 w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-800">
                Comparator / Control Arm
              </label>
              <input
                type="text"
                value={comparator}
                onChange={(e) => setComparator(e.target.value)}
                placeholder="e.g. Standard Care Metformin 500mg"
                className="mt-1 w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block font-semibold text-slate-800">
                Target Sample Size <span className="text-red-600">*</span>
              </label>
              <input
                type="number"
                required
                min={10}
                max={5000}
                value={targetEnrollment}
                onChange={(e) => setTargetEnrollment(e.target.value)}
                className="mt-1 w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>
            <div className="col-span-2">
              <label className="block font-semibold text-slate-800">
                Sponsor / Lead Institution <span className="text-red-600">*</span>
              </label>
              <input
                type="text"
                required
                value={sponsorName}
                onChange={(e) => setSponsorName(e.target.value)}
                className="mt-1 w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>
          </div>

          {/* ── Participating Hospital Institutions Selection ───────────────── */}
          <div className="border border-slate-300 bg-slate-50 p-3 space-y-2">
            <div className="flex items-center justify-between">
              <div>
                <label className="block font-bold text-slate-900 uppercase text-[11px] tracking-wide">
                  Participating Hospital Institutions &amp; Sites <span className="text-red-600">*</span>
                </label>
                <p className="text-[11px] text-slate-500">
                  Select which clinical research centers and hospitals are authorized under this trial protocol.
                </p>
              </div>
              <div className="flex items-center gap-2 text-[11px]">
                <button
                  type="button"
                  onClick={selectAllSites}
                  className="font-semibold text-slate-700 underline hover:text-black"
                >
                  Select All
                </button>
                <span className="text-slate-300">|</span>
                <button
                  type="button"
                  onClick={clearAllSites}
                  className="font-semibold text-slate-700 underline hover:text-black"
                >
                  Clear
                </button>
              </div>
            </div>

            {loadingSites ? (
              <p className="text-slate-500 italic py-2">Loading registered hospital institutions...</p>
            ) : availableInstitutions.length === 0 ? (
              <p className="text-amber-800 py-2">No institutions registered yet. A default central site will be created.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2 max-h-40 overflow-y-auto p-1 bg-white border border-slate-200">
                {availableInstitutions.map((inst) => {
                  const isChecked = selectedSiteIds.includes(inst.id)
                  return (
                    <label
                      key={inst.id}
                      className={`flex items-start gap-2.5 p-2 border cursor-pointer transition ${
                        isChecked
                          ? 'border-slate-800 bg-slate-50/80 text-slate-900'
                          : 'border-slate-200 bg-white text-slate-600 hover:border-slate-400'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleSite(inst.id)}
                        className="mt-0.5 h-3.5 w-3.5 rounded border-slate-300 text-slate-900 focus:ring-slate-900"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="font-bold truncate text-[11px]">
                          <span className="font-mono text-slate-500 mr-1">[{inst.site_code}]</span>
                          {inst.name}
                        </div>
                        <div className="text-[10px] text-slate-500 truncate">
                          {inst.city}, {inst.state} &bull; PI: {inst.pi_name || 'Assigned Investigator'}
                        </div>
                      </div>
                    </label>
                  )
                })}
              </div>
            )}
            <div className="text-[10px] text-slate-500">
              Selected: <strong>{selectedSiteIds.length}</strong> of {availableInstitutions.length} institutions. Target recruitment will be partitioned proportionally.
            </div>
          </div>

          <div className="border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-700">
            <strong>Regulatory Sequence Gate:</strong> Upon protocol creation, the trial will reside in <code>PLANNING</code> status. Institutional Ethics Committee (IEC) review and prospective CTRI registration are required before patient recruitment can be activated.
          </div>

          <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              className="border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy}
              className="border border-slate-800 bg-slate-900 px-5 py-2 text-xs font-semibold text-white hover:bg-black disabled:opacity-50"
            >
              {busy ? 'Registering Protocol...' : 'Register Protocol & Sites'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
