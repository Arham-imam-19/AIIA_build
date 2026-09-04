// The pieces every dashboard is built from.
//
// The backend sends the same shape to all five roles - a list of `tiles` (the big
// numbers) and a list of `blocks`, each tagged with a `kind`. So there is one
// renderer here per kind, and adding a panel to a role in a later phase is a
// change in Python only.
//
//     table      rows and columns
//     breakdown  a labelled list with proportions
//     series     points over time, drawn as a line chart
//     checklist  pass/fail items, for the compliance gates

import { useState } from 'react'
import { downloadSafetyReport } from './api'

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

// `tone` is the backend's opinion of whether a number is good news. It is only a
// hint - the colour, never the value.
const TONES = {
  good: 'text-emerald-700',
  warn: 'text-amber-700',
  bad: 'text-red-700',
  neutral: 'text-slate-900',
}

const TONE_RING = {
  good: 'border-emerald-200 bg-emerald-50/40',
  warn: 'border-amber-200 bg-amber-50/40',
  bad: 'border-red-200 bg-red-50/40',
  neutral: 'border-slate-200 bg-white',
}

export function Tile({ tile, changed }) {
  return (
    <div
      className={`rounded-lg border px-4 py-3 transition-colors duration-700 ${
        changed ? 'border-aiia-500 bg-aiia-50' : TONE_RING[tile.tone] || TONE_RING.neutral
      }`}
    >
      <div
        className={`whitespace-normal break-words text-2xl font-semibold tabular-nums tracking-tight ${
          TONES[tile.tone] || TONES.neutral
        }`}
        title={String(tile.value)}
      >
        {tile.value}
      </div>
      <div className="mt-0.5 text-xs font-medium text-slate-600">{tile.label}</div>
      {tile.hint && <div className="mt-0.5 text-xs text-slate-400">{tile.hint}</div>}
    </div>
  )
}

function Panel({ title, note, children, wide }) {
  return (
    <section
      className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm ${
        wide ? 'lg:col-span-2' : ''
      }`}
    >
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      {note && <p className="mt-0.5 text-xs text-slate-400">{note}</p>}
      <div className="mt-3">{children}</div>
    </section>
  )
}

// Cell values arrive as whatever the database holds: a number, a date string, a
// boolean rendered as "yes", or null for "not recorded". Only null needs help.
function Cell({ value }) {
  if (value === null || value === undefined || value === '')
    return <span className="text-slate-300">&mdash;</span>

  const valStr = String(value)
  if (valStr === 'EXPEDITED_DUE_SOON') {
    return (
      <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
        ⏱️ Due &lt;24h (Expedited)
      </span>
    )
  }
  if (valStr === 'EXPEDITED_OVERDUE') {
    return (
      <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800">
        🚨 Overdue &gt;24h (NDCT R42)
      </span>
    )
  }
  if (valStr === 'COMPLIANT_SUBMITTED') {
    return (
      <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">
        ✅ Reported to EC (Compliant)
      </span>
    )
  }
  if (valStr === 'NON_SERIOUS') {
    return (
      <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-normal text-slate-600">
        Routine (Non-Serious)
      </span>
    )
  }
  return <>{valStr}</>
}

function RowAction({ action, row }) {
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')
  const eventId = row[action.id_key]

  async function download() {
    setStatus('loading')
    setError('')
    try {
      await downloadSafetyReport(eventId)
      setStatus('done')
    } catch (err) {
      setError(err?.message || 'Download failed')
      setStatus('error')
    }
  }

  if (action.kind !== 'safety_report' || eventId === null || eventId === undefined) {
    return null
  }

  return (
    <div className="flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={download}
        disabled={status === 'loading'}
        className="whitespace-nowrap rounded-md border border-aiia-200 bg-aiia-50 px-2 py-1 text-xs font-medium text-aiia-700 hover:bg-aiia-100 disabled:cursor-wait disabled:opacity-60"
        aria-label={`Download safety report for event ${eventId}`}
      >
        {status === 'loading' ? 'Preparing...' : action.label || 'Download'}
      </button>
      {error && (
        <span className="max-w-32 text-xs text-red-600" title={error}>
          Download failed
        </span>
      )}
    </div>
  )
}

function Table({ block, wide }) {
  const rows = block.rows || []
  return (
    <Panel title={block.title} note={block.note} wide={wide}>
      {rows.length === 0 ? (
        <p className="py-4 text-sm text-slate-400">{block.empty || 'Nothing to show.'}</p>
      ) : (
        <div className="-mx-1 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-400">
                {block.columns.map((col) => (
                  <th key={col.key} className="whitespace-nowrap px-1 pb-2 font-medium">
                    {col.label}
                  </th>
                ))}
                {block.row_action && (
                  <th className="whitespace-nowrap px-1 pb-2 font-medium">
                    {block.row_action.label || 'Action'}
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className="border-t border-slate-100 align-top">
                  {/* Iterate the columns, not the row's own keys: a row carries
                      more fields than a given role is shown. */}
                  {block.columns.map((col) => (
                    <td
                      key={col.key}
                      className="px-1 py-2 text-slate-700"
                      style={{ maxWidth: '22rem' }}
                    >
                      <Cell value={row[col.key]} />
                    </td>
                  ))}
                  {block.row_action && (
                    <td className="px-1 py-2">
                      <RowAction action={block.row_action} row={row} />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  )
}

function Breakdown({ block, wide }) {
  return (
    <Panel title={block.title} note={block.note} wide={wide}>
      <ul className="space-y-2.5">
        {(block.items || []).map((item) => (
          <li key={item.label}>
            <div className="flex items-baseline justify-between text-sm">
              <span className="capitalize text-slate-700">
                {String(item.label).replace(/_/g, ' ')}
              </span>
              <span className="tabular-nums text-slate-500">
                {item.value}
                <span className="ml-1.5 text-xs text-slate-400">{item.percent}%</span>
              </span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-aiia-500"
                style={{ width: `${Math.min(item.percent, 100)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
      {block.total !== undefined && (
        <p className="mt-3 border-t border-slate-100 pt-2 text-xs text-slate-400">
          {block.total} in total
        </p>
      )}
    </Panel>
  )
}

const LINE_COLORS = ['#25734a', '#94a3b8', '#b45309']

function Series({ block, wide }) {
  const points = block.points || []
  return (
    <Panel title={block.title} note={block.note} wide={wide}>
      {points.length === 0 ? (
        <p className="py-4 text-sm text-slate-400">Nothing to plot yet.</p>
      ) : (
        <div className="h-56 w-full">
          <ResponsiveContainer>
            <LineChart data={points} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid stroke="#f1f5f9" />
              <XAxis
                dataKey={block.x || 'month'}
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                stroke="#e2e8f0"
              />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} stroke="#e2e8f0" />
              <Tooltip
                contentStyle={{ fontSize: 12, borderRadius: 8, borderColor: '#e2e8f0' }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {(block.lines || []).map((line, i) => (
                <Line
                  key={line.key}
                  type="monotone"
                  dataKey={line.key}
                  name={line.label}
                  stroke={LINE_COLORS[i % LINE_COLORS.length]}
                  strokeWidth={2}
                  strokeDasharray={i === 0 ? undefined : '4 3'}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  )
}

function Checklist({ block, wide }) {
  return (
    <Panel title={block.title} note={block.note} wide={wide}>
      <ul className="space-y-2">
        {(block.items || []).map((item) => (
          <li key={item.label} className="flex items-start gap-2.5 text-sm">
            <span
              className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-white ${
                item.ok ? 'bg-emerald-500' : 'bg-red-500'
              }`}
            >
              {item.ok ? '✓' : '✗'}
            </span>
            <span className="min-w-0">
              <span className="text-slate-700">{item.label}</span>
              {item.detail && (
                <span className="block text-xs text-slate-400">{item.detail}</span>
              )}
            </span>
          </li>
        ))}
      </ul>
      {block.total !== undefined && (
        <p className="mt-3 border-t border-slate-100 pt-2 text-xs text-slate-500">
          {block.passed} of {block.total} met
        </p>
      )}
    </Panel>
  )
}

const KINDS = { table: Table, breakdown: Breakdown, series: Series, checklist: Checklist }

export function Block({ block, wide }) {
  const Component = KINDS[block.kind]
  if (!Component) {
    // A kind the UI does not know yet. Say so rather than rendering nothing -
    // silence is how a missing panel goes unnoticed until the demo.
    return (
      <Panel title={block.title || block.key} wide={wide}>
        <p className="text-sm text-slate-400">
          No renderer for block kind &ldquo;{block.kind}&rdquo; yet.
        </p>
      </Panel>
    )
  }
  return <Component block={block} wide={wide} />
}
