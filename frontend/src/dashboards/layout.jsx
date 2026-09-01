// The frame all five dashboards share.
//
// The backend already decides *what* each role sees, so a role's file here only
// decides how it is laid out - which panel is worth the full width, and what to
// say about the screen. That keeps the five dashboards genuinely five screens
// without five copies of the same table code.

import { Block, Tile } from '../blocks'
import Simulate from '../Simulate'

function EventBanner({ event }) {
  if (!event) return null
  return (
    <div className="rounded-lg border border-aiia-500 bg-aiia-50 px-4 py-2.5 text-sm">
      <span className="font-medium text-aiia-700">Just now:</span>{' '}
      <span className="text-aiia-700">{event.message}</span>
      {event.actor && (
        <span className="text-aiia-600">
          {' '}
          &mdash; {event.actor.name} ({event.actor.role_label})
        </span>
      )}
      {event.detail_withheld && (
        <span className="ml-1 text-xs text-aiia-600">
          (details withheld: your role cannot open that record)
        </span>
      )}
    </div>
  )
}

export default function DashboardLayout({
  dashboard,
  changed,
  lastEvent,
  wide = [],
  note,
  simulateFirst = false,
  onExpired,
}) {
  const wideSet = new Set(wide)
  const simulate = <Simulate onExpired={onExpired} />

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-base font-semibold tracking-tight text-slate-900">
          {dashboard.title}
        </h2>
        <p className="text-sm text-slate-500">{dashboard.subtitle}</p>
        {note && <p className="mt-1.5 text-xs leading-relaxed text-slate-400">{note}</p>}
      </div>

      <EventBanner event={lastEvent} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {dashboard.tiles.map((tile) => (
          <Tile key={tile.key} tile={tile} changed={changed.has(tile.key)} />
        ))}
      </div>

      {simulateFirst && simulate}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {dashboard.blocks.map((block) => (
          <Block key={block.key} block={block} wide={wideSet.has(block.key)} />
        ))}
      </div>

      {!simulateFirst && simulate}
    </div>
  )
}
