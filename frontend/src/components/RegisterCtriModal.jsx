import React, { useState } from 'react'
import { updateTrialCtriRegistration } from '../api'

export default function RegisterCtriModal({ trial, onClose, onSuccess }) {
  const [ctriNumber, setCtriNumber] = useState(
    trial?.ctri_number || `CTRI/2026/${String(new Date().getMonth() + 1).padStart(2, '0')}/${String(Math.floor(10000 + Math.random() * 90000))}`
  )
  const [ctriDate, setCtriDate] = useState(trial?.ctri_registration_date || new Date().toISOString().split('T')[0])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!ctriNumber.trim()) {
      setError('Please enter a valid CTRI registration number.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await updateTrialCtriRegistration(trial.id, {
        ctri_number: ctriNumber.trim().toUpperCase(),
        ctri_registration_date: ctriDate,
      })
      onSuccess?.()
      onClose()
    } catch (err) {
      setError(err.detail || err.message || 'Failed to update CTRI registration')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4">
      <div className="w-full max-w-lg border border-slate-400 bg-white p-6 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 pb-3">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Government of India &middot; ICMR-NIMS / CDSCO Gate
            </div>
            <h2 className="text-base font-bold text-slate-900">
              Register Prospective CTRI Number
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 font-mono text-base font-bold"
          >
            ✕
          </button>
        </div>

        <p className="mt-2 text-xs text-slate-600 leading-relaxed">
          Under <strong>NDCT Rules 2019 (Rule 22)</strong>, all clinical trials in India must be prospectively registered on the Clinical Trials Registry - India (CTRI) before screening or enrolling the first human participant.
        </p>

        {error && (
          <div className="mt-3 border border-red-400 bg-red-50 p-2.5 text-xs text-red-900">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-3.5 text-xs">
          <div>
            <label className="block font-bold text-slate-800">
              Target Trial Protocol
            </label>
            <div className="mt-1 border border-slate-200 bg-slate-50 p-2 font-mono text-xs font-semibold text-slate-900">
              [{trial?.protocol_number}] {trial?.short_title || trial?.title}
            </div>
          </div>

          <div>
            <label className="block font-bold text-slate-800">
              CTRI Registration Number <span className="text-red-600">*</span>
            </label>
            <input
              type="text"
              required
              value={ctriNumber}
              onChange={(e) => setCtriNumber(e.target.value)}
              placeholder="e.g. CTRI/2026/03/012345"
              className="mt-1 w-full border border-slate-300 bg-white p-2 font-mono text-xs text-slate-900 uppercase focus:border-slate-800 focus:outline-none"
            />
            <span className="mt-0.5 block text-[10px] text-slate-500">
              Official registration code format: <code>CTRI/YYYY/MM/NNNNNN</code>
            </span>
          </div>

          <div>
            <label className="block font-bold text-slate-800">
              Prospective Registration Date <span className="text-red-600">*</span>
            </label>
            <input
              type="date"
              required
              max={new Date().toISOString().split('T')[0]}
              value={ctriDate}
              onChange={(e) => setCtriDate(e.target.value)}
              className="mt-1 w-full border border-slate-300 bg-white p-2 font-mono text-xs text-slate-900 focus:border-slate-800 focus:outline-none"
            />
            <span className="mt-0.5 block text-[10px] text-slate-500">
              Date registration was approved by ICMR-CTRI (cannot be in the future).
            </span>
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
              className="border border-slate-800 bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-black disabled:opacity-50"
            >
              {busy ? 'Saving...' : 'Save CTRI Registration'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
