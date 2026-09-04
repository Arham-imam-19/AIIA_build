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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4">
      <div className="w-full max-w-xl border border-slate-400 bg-white p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-200 pb-3">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Government of India &middot; Ministry of Ayush
            </div>
            <h3 className="text-sm font-bold uppercase tracking-wide text-slate-900 mt-0.5">
              Register Participating Hospital / Research Site
            </h3>
            <p className="text-xs text-slate-600">
              GCP-ASU Hospital Site Onboarding &amp; Principal Investigator Assignment
            </p>
          </div>
          <button
            onClick={onClose}
            className="border border-slate-300 bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700 hover:bg-slate-200"
          >
            ✕
          </button>
        </div>

        {trials.length === 0 && (
          <div className="mt-3 border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 leading-relaxed space-y-1">
            <div className="font-bold flex items-center gap-1.5">
              <span>⚠️</span> No Active Trial Protocols Found
            </div>
            <div>
              Under Good Clinical Practice (GCP) and Indian NDCT Rules 2019, a participating hospital research site cannot exist in isolation &mdash; it must be affiliated with an approved <strong>Clinical Trial Protocol</strong>.
            </div>
            <div className="pt-1 text-[11px] font-semibold text-amber-800">
              Please go to <em>System Governance &amp; Protocols</em> and click <strong>+ Register New Protocol</strong> first.
            </div>
          </div>
        )}

        {error && (
          <div className="mt-3 border border-red-600 bg-red-50 p-3 text-xs font-medium text-red-900">
            {typeof error === 'string' ? error : JSON.stringify(error)}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-800">
                Associated Trial Protocol <span className="text-red-600">*</span>
              </label>
              <select
                value={trialId}
                onChange={(e) => setTrialId(e.target.value)}
                disabled={trials.length === 0}
                className="mt-1 w-full border border-slate-300 bg-white p-2 text-xs font-medium text-slate-900 focus:border-slate-800 focus:outline-none disabled:bg-slate-100 disabled:text-slate-400"
                required
              >
                {trials.length === 0 ? (
                  <option value="">-- No protocols registered --</option>
                ) : (
                  trials.map((t) => (
                    <option key={t.id} value={t.id}>
                      [{t.protocol_number}] {t.short_title || t.title} ({t.phase?.toUpperCase()})
                    </option>
                  ))
                )}
              </select>
            </div>
            <div>
              <label className="block font-semibold text-slate-800">
                Site Code (2-Digits) <span className="text-red-600">*</span>
              </label>
              <input
                type="text"
                required
                value={siteCode}
                onChange={(e) => setSiteCode(e.target.value)}
                placeholder="e.g. 02"
                className="mt-1 w-full border border-slate-300 bg-white p-2 font-mono font-bold text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-800">
              Hospital / Institute Full Official Name <span className="text-red-600">*</span>
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. National Institute of Ayurveda (NIA), Jaipur"
              className="mt-1 w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-800">
                City <span className="text-red-600">*</span>
              </label>
              <input
                type="text"
                required
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="e.g. Jaipur"
                className="mt-1 w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-800">
                State <span className="text-red-600">*</span>
              </label>
              <input
                type="text"
                required
                value={state}
                onChange={(e) => setState(e.target.value)}
                placeholder="e.g. Rajasthan"
                className="mt-1 w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-800">
                Principal Investigator (PI) Full Name <span className="text-red-600">*</span>
              </label>
              <input
                type="text"
                required
                value={piName}
                onChange={(e) => setPiName(e.target.value)}
                placeholder="e.g. Prof. Sanjeev Sharma"
                className="mt-1 w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-800">
                PI Official Email Address
              </label>
              <input
                type="email"
                value={piEmail}
                onChange={(e) => setPiEmail(e.target.value)}
                placeholder="pi.nia@aiia-ctms.in"
                className="mt-1 w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-800">
                Contact Phone Number
              </label>
              <input
                type="tel"
                value={contactPhone}
                onChange={(e) => setContactPhone(e.target.value)}
                placeholder="+91 141 2635816"
                className="mt-1 w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-800">
                Target Recruitment Quota <span className="text-red-600">*</span>
              </label>
              <input
                type="number"
                min={5}
                max={1000}
                value={targetEnrollment}
                onChange={(e) => setTargetEnrollment(e.target.value)}
                className="mt-1 w-full border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
              />
            </div>
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
              {busy ? 'Registering...' : 'Register Study Site'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
