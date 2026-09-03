import React, { useState, useEffect } from 'react'
import { api } from '../api'

export default function Pharmacovigilance() {
  const [aes, setAes] = useState([])
  const [loading, setLoading] = useState(false)
  const [code, setCode] = useState('')
  const [activeEvent, setActiveEvent] = useState(null)
  const [busy, setBusy] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const res = await api('/api/adverse-events?size=100')
      setAes(res.items || [])
    } catch(e) {}
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  async function applyCode(e) {
    e.preventDefault()
    setBusy(true)
    try {
      await api(`/api/adverse-events/${activeEvent.id}/code`, {
        method: 'PATCH',
        body: { meddra_code: code }
      })
      alert('MedDRA code successfully applied!')
      setActiveEvent(null)
      setCode('')
      await load()
    } catch(err) {
      alert('Failed: ' + err.message)
    }
    setBusy(false)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between rounded-lg border border-indigo-200 bg-indigo-50 p-4 shadow-sm">
        <div>
          <h2 className="text-xl font-bold text-indigo-800">Pharmacovigilance (NPvCC) Medical Coding</h2>
          <p className="text-sm text-indigo-600">Map raw clinical symptoms to the official MedDRA dictionary.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-5 shadow-sm overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
            <thead>
              <tr className="bg-slate-50 text-slate-600">
                <th className="px-3 py-2">Event</th>
                <th className="px-3 py-2">Symptom (Verbatim)</th>
                <th className="px-3 py-2">Severity</th>
                <th className="px-3 py-2">MedDRA Code</th>
                <th className="px-3 py-2">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {aes.map(ae => (
                <tr key={ae.id} className="hover:bg-slate-50">
                  <td className="px-3 py-2 font-mono">AE-{ae.id}</td>
                  <td className="px-3 py-2 font-bold">{ae.term_verbatim}</td>
                  <td className="px-3 py-2">{ae.severity}</td>
                  <td className="px-3 py-2 font-mono text-indigo-600">{ae.meddra_code || 'UNCODED'}</td>
                  <td className="px-3 py-2">
                    <button 
                      onClick={() => setActiveEvent(ae)}
                      className="bg-indigo-100 text-indigo-700 px-2 py-1 rounded text-[10px] font-bold hover:bg-indigo-200"
                    >
                      CODE
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {activeEvent && (
          <div className="rounded-xl border-2 border-indigo-500 bg-indigo-50 p-5 shadow-sm h-fit">
            <h3 className="font-bold text-indigo-900 mb-2">Coding AE-{activeEvent.id}</h3>
            <p className="text-sm text-indigo-800 mb-4 font-medium">"{activeEvent.term_verbatim}"</p>
            <form onSubmit={applyCode}>
              <label className="block text-xs font-bold text-indigo-700 mb-1">Enter WHO MedDRA Code</label>
              <input 
                type="text" 
                required 
                value={code} 
                onChange={e => setCode(e.target.value)}
                placeholder="e.g. 10019211" 
                className="w-full px-3 py-2 border border-indigo-300 rounded mb-4"
              />
              <button disabled={busy} type="submit" className="w-full bg-indigo-600 text-white font-bold py-2 rounded hover:bg-indigo-700">
                {busy ? 'Saving...' : 'Apply Code'}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  )
}
