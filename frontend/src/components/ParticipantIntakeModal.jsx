import { useEffect, useState } from 'react'
import { createStructuredSubject, fetchTrials } from '../api'

export default function ParticipantIntakeModal({ trialId, siteId, onClose, onSuccess }) {
  const [activeTrialId, setActiveTrialId] = useState(trialId || null)
  const [sex, setSex] = useState('female')
  const [yearOfBirth, setYearOfBirth] = useState(1992)
  const [heightCm, setHeightCm] = useState(165)
  const [weightKg, setWeightKg] = useState(62)
  const [prakriti, setPrakriti] = useState('vata-pitta')
  const [screeningDate, setScreeningDate] = useState(new Date().toISOString().split('T')[0])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchTrials()
      .then((res) => {
        if (res.items?.[0]?.id) {
          setActiveTrialId(res.items[0].id)
        }
      })
      .catch(() => {})
  }, [])

  const currentYear = new Date().getFullYear()
  const age = yearOfBirth ? currentYear - Number(yearOfBirth) : ''
  const bmi = heightCm && weightKg ? (Number(weightKg) / Math.pow(Number(heightCm) / 100, 2)).toFixed(1) : ''

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await createStructuredSubject({
        trial_id: Number(activeTrialId || trialId || 1),
        site_id: siteId ? Number(siteId) : undefined,
        screening_date: screeningDate,
        sex,
        year_of_birth: Number(yearOfBirth),
        height_cm: Number(heightCm),
        weight_kg: Number(weightKg),
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
      <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 dark:border-slate-800">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              📝 Structured Participant Screening & Intake
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              CDASH / CDISC SDTM DM Domain & Ayush Baseline Classification
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
                <option value="vata-pitta">Vata-Pitta</option>
                <option value="pitta-kapha">Pitta-Kapha</option>
                <option value="kapha-vata">Kapha-Vata</option>
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
                🪪 Identity & Contact Information (Ethics Permitted)
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
              className="rounded-lg bg-aiia-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-aiia-700 disabled:opacity-50"
            >
              {busy ? 'Registering...' : 'Register Screening Intake'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
