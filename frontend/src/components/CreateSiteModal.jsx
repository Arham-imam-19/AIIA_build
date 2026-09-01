import { useEffect, useState } from 'react'
import { createSite, fetchTrials } from '../api'

export default function CreateSiteModal({ onClose, onSuccess }) {
  const [trials, setTrials] = useState([])
  const [trialId, setTrialId] = useState('')
  const [siteCode, setSiteCode] = useState('02')
  const [name, setName] = useState('')
  const [city, setCity] = useState('New Delhi')
  const [state, setState] = useState('Delhi')
  const [piName, setPiName] = useState('')
  const [piEmail, setPiEmail] = useState('')
  const [contactPhone, setContactPhone] = useState('')
  const [targetEnrollment, setTargetEnrollment] = useState(25)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchTrials()
      .then((res) => {
        if (res.items?.length) {
          setTrials(res.items)
          setTrialId(res.items[0].id)
        }
      })
      .catch(() => {})
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)

    try {
      await createSite({
        trial_id: Number(trialId),
        site_code: siteCode.trim().toUpperCase(),
        name: name.trim(),
        city: city.trim(),
        state: state.trim(),
        country: 'India',
        pi_name: piName.trim(),
        pi_email: piEmail.trim().toLowerCase() || undefined,
        contact_phone: contactPhone.trim() || undefined,
        target_enrollment: Number(targetEnrollment),
        status: 'activated',
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
      <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 dark:border-slate-800">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              🏥 Register Participating Study Site / Hospital
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              GCP-ASU Hospital Site Onboarding & Principal Investigator Assignment
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
                Associated Trial Protocol
              </label>
              <select
                value={trialId}
                onChange={(e) => setTrialId(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs font-medium text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                required
              >
                {trials.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.protocol_number} ({t.phase})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Site Code (2-Digits)
              </label>
              <input
                type="text"
                required
                value={siteCode}
                onChange={(e) => setSiteCode(e.target.value)}
                placeholder="e.g. 02"
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs font-mono font-bold text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
          </div>

          <div>
            <label className="block font-medium text-slate-700 dark:text-slate-300">
              Hospital / Institute Full Name
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. National Institute of Ayurveda (NIA), Jaipur"
              className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                City
              </label>
              <input
                type="text"
                required
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="e.g. Jaipur"
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                State
              </label>
              <input
                type="text"
                required
                value={state}
                onChange={(e) => setState(e.target.value)}
                placeholder="e.g. Rajasthan"
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Principal Investigator (PI) Full Name
              </label>
              <input
                type="text"
                required
                value={piName}
                onChange={(e) => setPiName(e.target.value)}
                placeholder="e.g. Prof. Sanjeev Sharma"
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                PI Email Address
              </label>
              <input
                type="email"
                value={piEmail}
                onChange={(e) => setPiEmail(e.target.value)}
                placeholder="pi.nia@aiia-ctms.in"
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Contact Phone
              </label>
              <input
                type="tel"
                value={contactPhone}
                onChange={(e) => setContactPhone(e.target.value)}
                placeholder="+91 141 2635816"
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300">
                Target Recruitment Quota
              </label>
              <input
                type="number"
                min={5}
                max={1000}
                value={targetEnrollment}
                onChange={(e) => setTargetEnrollment(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              />
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
              className="rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-teal-700 disabled:opacity-50"
            >
              {busy ? 'Registering...' : 'Register Study Site'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
