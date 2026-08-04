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

      <div className="mt-3 flex items-baseline gap-1.5">
        <span className="readout text-3xl font-semibold text-ink">{value}</span>
        {unit && <span className="text-sm font-medium text-ink-3">{unit}</span>}
      </div>

      {hint && <p className="mt-1.5 text-xs text-ink-3">{hint}</p>}
    </GlassCard>
  )
}
