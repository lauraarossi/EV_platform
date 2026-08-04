import type { Vehicle } from '../types'

/** Segmented control when there are few vehicles, dropdown when there are many. */
export default function VehiclePicker({
  vehicles,
  value,
  onChange,
  label = 'Vehicle',
}: {
  vehicles: Vehicle[]
  value: number
  onChange: (id: number) => void
  label?: string
}) {
  if (vehicles.length <= 1) return null

  const name = (v: Vehicle) => v.nickname || `${v.make} ${v.model}`

  if (vehicles.length <= 3) {
    return (
      <div role="group" aria-label={label} className="glass inline-flex gap-1 rounded-xl p-1">
        {vehicles.map(v => {
          const active = v.id === value
          return (
            <button
              key={v.id}
              onClick={() => onChange(v.id)}
              aria-pressed={active}
              className={`focus-ring rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                active ? 'text-ink' : 'text-ink-3 hover:text-ink-2'
              }`}
              style={
                active
                  ? {
                      background: 'color-mix(in oklab, var(--accent) 18%, transparent)',
                      border: '1px solid color-mix(in oklab, var(--accent) 35%, transparent)',
                    }
                  : { border: '1px solid transparent' }
              }
            >
              {name(v)}
            </button>
          )
        })}
      </div>
    )
  }

  return (
    <label className="inline-flex items-center gap-2">
      <span className="text-[11px] uppercase tracking-wider text-ink-3">{label}</span>
      <select
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="focus-ring rounded-lg border border-edge bg-surface-solid px-3 py-1.5 text-sm text-ink"
      >
        {vehicles.map(v => (
          <option key={v.id} value={v.id}>{name(v)}</option>
        ))}
      </select>
    </label>
  )
}
