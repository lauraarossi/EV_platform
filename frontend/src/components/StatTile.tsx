import GlassCard from './GlassCard'

/**
 * A single headline number. Per the viz guidance a lone magnitude is a stat
 * tile, not a chart — so there is no plot and no series colour here; the value
 * wears ink tokens and the accent appears only as a small identifying mark.
 */
export default function StatTile({
  label,
  value,
  unit,
  hint,
  accent = 'var(--accent)',
}: {
  label: string
  value: string
  unit?: string
  hint?: string
  accent?: string
}) {
  return (
    <GlassCard interactive className="p-5">
      <div className="flex items-center gap-2">
        <span
          aria-hidden="true"
          className="h-1.5 w-1.5 rounded-full"
          style={{ background: accent, boxShadow: `0 0 10px ${accent}` }}
        />
        <span className="text-xs font-medium uppercase tracking-wider text-ink-3">{label}</span>
      </div>

      {/* min-w-0 lets the value shrink inside the grid cell instead of pushing
          past it, and the size steps down on narrow screens. */}
      <div className="mt-3 flex min-w-0 flex-wrap items-baseline gap-x-1.5">
        <span className="readout min-w-0 truncate text-2xl font-semibold text-ink sm:text-3xl">
          {value}
        </span>
        {unit && <span className="shrink-0 text-sm font-medium text-ink-3">{unit}</span>}
      </div>

      {hint && <p className="mt-1.5 text-xs text-ink-3">{hint}</p>}
    </GlassCard>
  )
}
