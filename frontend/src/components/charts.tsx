import type { ReactNode } from 'react'
import GlassCard from './GlassCard'

/** Shared chart chrome. Axes and grid stay recessive so the marks lead. */
export const axisProps = {
  stroke: 'var(--ink-3)',
  tick: { fill: 'var(--ink-3)', fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: 'var(--border)' },
}

export const gridProps = {
  stroke: 'var(--border)',
  strokeDasharray: '0',
  vertical: false,
}

export function ChartCard({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string
  subtitle?: string
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <GlassCard className="p-5">
      <div className="mb-4">
        {/* One series per chart, so the title names it and no legend box is needed. */}
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xs text-ink-3">{subtitle}</p>}
      </div>
      {children}
      {footer && <div className="mt-3 text-xs text-ink-3">{footer}</div>}
    </GlassCard>
  )
}

export function Tip({
  active,
  payload,
  label,
  unit,
  labelPrefix = '',
}: {
  active?: boolean
  payload?: { value: number; payload: Record<string, unknown> }[]
  label?: string | number
  unit: string
  labelPrefix?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="glass rounded-lg px-3 py-2 text-xs">
      <p className="text-ink-3">{labelPrefix}{label}</p>
      <p className="readout mt-0.5 font-semibold text-ink">
        {payload[0].value} {unit}
      </p>
    </div>
  )
}
