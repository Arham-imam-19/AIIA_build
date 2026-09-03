import React, { useState, useEffect } from 'react'
import { api, fetchTrials } from '../api'

export default function DSMB() {
  const [trial, setTrial] = useState(null)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  
  async function load() {
    setLoading(true)
    try {
      const res = await fetchTrials()
      if (res.items && res.items.length > 0) setTrial(res.items[0])
    } catch(e) {}
    setLoading(false)
  }
  
  useEffect(() => { load() }, [])

  async function haltTrial() {
    if(!confirm('EMERGENCY: Are you sure you want to halt the trial globally?')) return;
    setBusy(true)
    try {
      await api(`/api/trials/${trial.id}/halt`, { method: 'POST' })
      alert('TRIAL SUCCESSFULLY HALTED.')
      await load()
    } catch(e) {
      alert('Failed to halt: ' + e.message)
    }
    setBusy(false)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 p-4 shadow-sm">
        <div>
          <h2 className="text-xl font-bold text-red-800">DSMB Master Control</h2>
          <p className="text-sm text-red-600">You have global authority to halt this trial if statistical safety bounds are breached.</p>
        </div>
      </div>

      <div className="rounded-xl border-2 border-slate-200 bg-white p-8 text-center shadow-sm">
        <h3 className="text-2xl font-bold text-slate-800 mb-4">Trial Status: {trial?.status ? trial.status.toUpperCase() : 'LOADING...'}</h3>
        <button 
          onClick={haltTrial}
          disabled={busy || trial?.status === 'suspended'}
          className="bg-red-600 text-white text-2xl font-black py-6 px-12 rounded-xl shadow-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          🚨 EMERGENCY HALT TRIAL
        </button>
      </div>
    </div>
  )
}
