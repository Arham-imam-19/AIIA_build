// The "make something happen" panel - what turns the live update from a claim
// into a demo.
//
// These buttons write real rows: a new participant, a new adverse event, a visit
// recorded outside its window. Every one is attributed in the audit trail, and
// every open dashboard recomputes. Nothing here is a fake number on a timer.
//
// A role that may not write trial data gets the buttons greyed out with the
// server's own explanation. That is a courtesy: the API would refuse the request
// anyway, which is where the actual enforcement lives.

import { useEffect, useState } from 'react'
import { simulate, simulateOptions } from './api'

export default function Simulate({ onExpired }) {
  const [options, setOptions] = useState(null)
  const [busy, setBusy] = useState(null)
  const [result, setResult] = useState(null)
  const [failed, setFailed] = useState(null)

  useEffect(() => {
    simulateOptions()
      .then(setOptions)
      .catch((err) => {
        if (err.status === 401 && onExpired) onExpired()
        setFailed(err.detail)
      })
  }, [onExpired])

  async function fire(action) {
    setBusy(action.key)
    setFailed(null)
    setResult(null)
    try {
      const created = await simulate(action.key)
      setResult({ action, created })
    } catch (err) {
      if (err.status === 401 && onExpired) onExpired()
      setFailed(err.detail)
    } finally {
      setBusy(null)
    }
  }

  async function fireSerious() {
    const action = options.actions.find((a) => a.key === 'adverse-event')
    setBusy('serious')
    setFailed(null)
    setResult(null)
    try {
      const created = await simulate('adverse-event', { serious: true })
      setResult({ action: { ...action, label: 'Report a SERIOUS adverse event' }, created })
    } catch (err) {
      if (err.status === 401 && onExpired) onExpired()
      setFailed(err.detail)
    } finally {
      setBusy(null)
    }
  }

  if (!options) {
    return (
      <div className="rounded-xl border border-dashed border-slate-200 p-5 text-sm text-slate-400">
        {failed || 'Loading demo controls…'}
      </div>
    )
  }

  const canWriteAe = options.actions.find((a) => a.key === 'adverse-event')?.allowed
  const blocked = options.actions.find((a) => !a.allowed)

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-sm font-semibold text-slate-800">Simulate an event</h3>
      <p className="mt-0.5 text-xs text-slate-400">
        Writes a real row, records it in the audit trail, and pushes the new numbers
        to every open dashboard.
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        {options.actions.map((action) => (
          <button
            key={action.key}
            onClick={() => fire(action)}
            disabled={!action.allowed || busy !== null}
            title={action.why_not || `Moves: ${action.moves}`}
            className="rounded-lg border border-aiia-600 bg-aiia-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-aiia-700 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
          >
            {busy === action.key ? 'Working…' : action.label}
          </button>
        ))}
        {canWriteAe && (
          <button
            onClick={fireSerious}
            disabled={busy !== null}
            title="A serious event starts a reporting clock - this is the one the Ethics Committee and Regulator screens react to."
            className="rounded-lg border border-red-600 bg-white px-3 py-1.5 text-xs font-medium text-red-700 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
          >
            {busy === 'serious' ? 'Working…' : 'Report a SERIOUS event'}
          </button>
        )}
      </div>

      {blocked && (
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-500">
          {blocked.why_not}
        </p>
      )}

      {failed && (
        <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{failed}</p>
      )}

      {result && (
        <div className="mt-3 rounded-lg bg-aiia-50 px-3 py-2 text-xs text-aiia-700">
          <div className="font-medium">{result.created.event.message}</div>
          <div className="mt-0.5 text-aiia-600">
            Written to the database and the audit trail. Moves: {result.action.moves}
          </div>
        </div>
      )}

      <p className="mt-3 border-t border-slate-100 pt-2 text-xs text-slate-400">
        {options.note}
      </p>
    </section>
  )
}
