import { useEffect, useState } from 'react'
import { createStructuredSubject, fetchTrials, fetchSites } from '../api'
import { useAuth } from '../auth'

export default function ParticipantIntakeModal({ trialId, siteId, onClose, onSuccess }) {
  const { user } = useAuth()

  const [trials, setTrials] = useState([])
  const [sites, setSites] = useState([])
  const [selectedTrialId, setSelectedTrialId] = useState(trialId || null)
  const [selectedSiteId, setSelectedSiteId] = useState(siteId || null)
  const [loadingMeta, setLoadingMeta] = useState(true)

  const [sex, setSex] = useState('female')
  const [yearOfBirth, setYearOfBirth] = useState(1992)
  const [heightCm, setHeightCm] = useState(165)
  const [weightKg, setWeightKg] = useState(62)
  const [prakriti, setPrakriti] = useState('vata_pitta')
  const [screeningDate, setScreeningDate] = useState(new Date().toISOString().split('T')[0])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let isMounted = true
    Promise.all([fetchTrials(), fetchSites()])
      .then(([trialsRes, sitesRes]) => {
        if (!isMounted) return
        const trialList = trialsRes.items || []
        const siteList = sitesRes.items || []
        setTrials(trialList)
        setSites(siteList)

        // Select default trial
        const defaultTrial =
          (trialId && trialList.find((t) => t.id === Number(trialId))) ||
          trialList.find((t) => t.status === 'recruiting') ||
          trialList[0] ||
          null

        if (defaultTrial) {
          setSelectedTrialId(defaultTrial.id)
          // Find matching site
          const userBaseSite = siteList.find((s) => s.id === user?.site_id)
          const userSiteCode = userBaseSite?.site_code
          const matchingSite =
            (userSiteCode && siteList.find((s) => s.trial_id === defaultTrial.id && s.site_code === userSiteCode)) ||
            siteList.find((s) => s.trial_id === defaultTrial.id && s.id === user?.site_id) ||
            userBaseSite ||
            siteList.find((s) => s.trial_id === defaultTrial.id) ||
            siteList[0]
          setSelectedSiteId(matchingSite?.id || siteId || null)
        }
        setLoadingMeta(false)
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.detail || err.message || 'Failed to load study metadata')
          setLoadingMeta(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [trialId, siteId, user])

  const selectedTrial = trials.find((t) => t.id === Number(selectedTrialId)) || trials[0]
  const availableSites = sites.filter((s) => s.trial_id === Number(selectedTrialId))
  const selectedSite =
    availableSites.find((s) => s.id === Number(selectedSiteId)) || availableSites[0]

  const handleTrialChange = (newTrialId) => {
    const tId = Number(newTrialId)
    setSelectedTrialId(tId)
    const sitesForTrial = sites.filter((s) => s.trial_id === tId)
    const userBaseSite = sites.find((s) => s.id === user?.site_id)
    const userSiteCode = userBaseSite?.site_code
    const userSiteMatch =
      (userSiteCode && sitesForTrial.find((s) => s.site_code === userSiteCode)) ||
      sitesForTrial.find((s) => s.id === user?.site_id) ||
      userBaseSite ||
      sitesForTrial[0]
    setSelectedSiteId(userSiteMatch?.id || null)
    setError(null)
  }

  const currentYear = new Date().getFullYear()
  const age = yearOfBirth ? currentYear - Number(yearOfBirth) : ''
  const bmi =
    heightCm && weightKg
      ? (Number(weightKg) / Math.pow(Number(heightCm) / 100, 2)).toFixed(1)
      : ''

  const isRecruiting = selectedTrial?.status === 'recruiting'
  const isEthicsApproved = selectedTrial?.ethics_approval_status === 'approved'

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)

    if (!isEthicsApproved) {
      setError(
        `Enrollment Blocked: Protocol ${selectedTrial?.protocol_number} ethics approval status is ${selectedTrial?.ethics_approval_status || 'Pending'}. IEC clearance required before screening.`
      )
      setBusy(false)
      return
    }

    if (!isRecruiting) {
      setError(
        `Enrollment Blocked: Protocol ${selectedTrial?.protocol_number} is in '${selectedTrial?.status}' status. Only recruiting trials can screen participants.`
      )
      setBusy(false)
      return
    }

    try {
      await createStructuredSubject({
        trial_id: Number(selectedTrialId || selectedTrial?.id || 1),
        site_id: selectedSite?.id ? Number(selectedSite.id) : undefined,
        screening_date: screeningDate,
        sex,
        year_of_birth: Number(yearOfBirth),
        height_cm: Number(heightCm),
        weight_kg: Number(weightKg),
        prakriti: prakriti ? prakriti.replace('-', '_') : undefined,
      })
      onSuccess?.()
      onClose()
    } catch (err) {
      setError(err.detail || err.message || 'Failed to register participant screening record.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 dark:border-slate-800">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              📝 Structured Participant Screening &amp; Intake
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              CDASH / CDISC SDTM DM Domain &middot; Multi-Protocol Clinical Intake
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 font-bold"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="mt-3 rounded-lg bg-red-50 border border-red-200 p-3 text-xs font-semibold text-red-700 dark:bg-red-950 dark:text-red-300">
            ⚠️ {typeof error === 'string' ? error : JSON.stringify(error)}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4 text-xs">
          {/* Protocol Selection & Status Card */}
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 dark:border-slate-800 dark:bg-slate-800/60 space-y-3">
            <div className="flex items-center justify-between">
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                1. Select Study Protocol / Clinical Trial
              </label>
              <span className="text-[10px] font-mono font-semibold text-slate-500">
                Total Available: {trials.length}
              </span>
            </div>

            <select
              value={selectedTrialId || ''}
              onChange={(e) => handleTrialChange(e.target.value)}
              disabled={loadingMeta}
              className="w-full rounded-lg border border-slate-300 bg-white p-2 text-xs font-semibold text-slate-900 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            >
              {trials.map((t) => (
                <option key={t.id} value={t.id}>
                  [{t.protocol_number}] {t.title} &middot; ({t.status.toUpperCase()})
                </option>
              ))}
            </select>

            {selectedTrial && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                <div className="rounded border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900">
                  <span className="block text-[9px] uppercase font-bold text-slate-400">Protocol ID</span>
                  <span className="font-mono text-[11px] font-bold text-slate-900 dark:text-slate-100 truncate block">
                    {selectedTrial.protocol_number}
                  </span>
                </div>
                <div className="rounded border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900">
                  <span className="block text-[9px] uppercase font-bold text-slate-400">CTRI Number</span>
                  <span className="font-mono text-[11px] font-semibold text-slate-700 dark:text-slate-300 truncate block">
                    {selectedTrial.ctri_number || 'Prospective Reg.'}
                  </span>
                </div>
                <div className="rounded border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900">
                  <span className="block text-[9px] uppercase font-bold text-slate-400">IEC Clearance</span>
                  <span className={`text-[10px] font-bold block ${isEthicsApproved ? 'text-emerald-700 dark:text-emerald-400' : 'text-amber-700 dark:text-amber-400'}`}>
                    {isEthicsApproved ? '✓ Cleared' : '⏳ Pending'}
                  </span>
                </div>
                <div className="rounded border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900">
                  <span className="block text-[9px] uppercase font-bold text-slate-400">Recruitment</span>
                  <span className={`text-[10px] font-bold block ${isRecruiting ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400'}`}>
                    {selectedTrial.status?.toUpperCase()}
                  </span>
                </div>
              </div>
            )}

            {/* Site selector if multiple sites exist for this trial */}
            {availableSites.length > 1 && (
              <div className="pt-1">
                <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">
                  Assigned Participating Site / Hospital
                </label>
                <select
                  value={selectedSiteId || ''}
                  onChange={(e) => setSelectedSiteId(Number(e.target.value))}
                  className="w-full rounded-lg border border-slate-200 p-1.5 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                >
                  {availableSites.map((s) => (
                    <option key={s.id} value={s.id}>
                      Site {s.id} ({s.site_code}) &middot; {s.name} ({s.city})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Demographics */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Biological Sex
              </label>
              <select
                value={sex}
                onChange={(e) => setSex(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs font-medium text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Year of Birth (Age: {age} yrs)
              </label>
              <input
                type="number"
                min={1920}
                max={currentYear - 18}
                value={yearOfBirth}
                onChange={(e) => setYearOfBirth(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Height (cm)
              </label>
              <input
                type="number"
                step="0.1"
                min={100}
                max={250}
                value={heightCm}
                onChange={(e) => setHeightCm(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                required
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Weight (kg)
              </label>
              <input
                type="number"
                step="0.1"
                min={30}
                max={200}
                value={weightKg}
                onChange={(e) => setWeightKg(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                required
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Calculated BMI
              </label>
              <input
                type="text"
                readOnly
                value={bmi ? `${bmi} kg/m²` : '-'}
                className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs font-bold text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Ayurvedic Prakriti (Constitution)
              </label>
              <select
                value={prakriti}
                onChange={(e) => setPrakriti(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs font-medium text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                <option value="vata_pitta">Vata-Pitta</option>
                <option value="pitta_kapha">Pitta-Kapha</option>
                <option value="kapha_vata">Kapha-Vata</option>
                <option value="tridoshic">Tridoshic (Samadosha)</option>
              </select>
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Screening Date
              </label>
              <input
                type="date"
                max={new Date().toISOString().split('T')[0]}
                value={screeningDate}
                onChange={(e) => setScreeningDate(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                required
              />
            </div>
          </div>

          {/* Ethics-Permitted Participant Identity & Contact Section */}
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 dark:border-slate-800 dark:bg-slate-800/40 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-bold text-xs text-slate-900 dark:text-white flex items-center gap-1.5">
                🪪 Identity &amp; Contact Information (Ethics Permitted)
              </span>
              <span className="text-[10px] text-emerald-700 font-semibold dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/80 px-2 py-0.5 rounded">
                DPDP Act 2023 Sec 6
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 text-[11px]">
                  Participant Full Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Ramesh Sharma"
                  className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 text-[11px]">
                  Phone Number
                </label>
                <input
                  type="tel"
                  placeholder="+91 98765 43210"
                  className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 text-[11px]">
                  Email Address
                </label>
                <input
                  type="email"
                  placeholder="patient@example.in"
                  className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                />
              </div>
            </div>

            <div className="text-[10px] text-slate-500 leading-relaxed">
              🔒 <strong>Ethics Notice:</strong> Contact details are encrypted at rest and accessible exclusively by assigned site clinical investigators for study appointments. External regulatory and sponsor oversight dashboards display pseudonymized codes only.
            </div>
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
              className="rounded-lg bg-aiia-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-aiia-700 disabled:opacity-50 transition"
            >
              {busy ? 'Registering...' : 'Register Screening Intake'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
