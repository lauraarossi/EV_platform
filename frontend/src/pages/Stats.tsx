import { useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Cell,
} from 'recharts'
import { getVehicles } from '../api/vehicles'
import { getIntervals, getSummary } from '../api/stats'
import { getChargingSessions } from '../api/charging'
import { CHARGER_LABEL, type ChargerType } from '../types'
import { useAsync } from '../hooks/useAsync'
import PageHeader from '../components/PageHeader'
import GlassCard from '../components/GlassCard'
import StatTile from '../components/StatTile'
import VehiclePicker from '../components/VehiclePicker'
import { ChartCard, Tip, axisProps, gridProps } from '../components/charts'
import { Loading, ErrorState, EmptyState } from '../components/States'

const shortDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-IE', { day: 'numeric', month: 'short' })

export default function Stats() {
  const [vehicleId, setVehicleId] = useState<number | null>(null)

  const { data, error, loading, reload } = useAsync(async () => {
    const vehicles = await getVehicles()
    const owned = vehicles.filter(v => !v.is_comparison_vehicle)
    const selected = vehicleId ?? owned[0]?.id ?? null
    if (!selected) return { owned, selected, summary: null, intervals: [], sessions: [] }
    const [summary, iv, sessions] = await Promise.all([
      getSummary(selected),
      getIntervals(selected),
      getChargingSessions(selected),
    ])
    return { owned, selected, summary, intervals: iv.intervals, sessions }
  }, [vehicleId])

  if (loading) return <Loading label="Crunching your numbers…" />
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (!data) return null

  const { owned, selected, summary, intervals, sessions } = data

  if (owned.length === 0) {
    return (
      <>
        <PageHeader title="Stats" subtitle="What your EV actually costs to run." />
        <EmptyState title="Add a vehicle first" body="Stats appear once you have a car and a couple of charges logged." />
      </>
    )
  }

  if (!summary || summary.interval_count === 0) {
    return (
      <>
        <PageHeader title="Stats" subtitle="What your EV actually costs to run." />
        {owned.length > 1 && (
          <div className="mb-4">
            <VehiclePicker vehicles={owned} value={selected!} onChange={setVehicleId} />
          </div>
        )}
        <EmptyState
          title="Not enough data yet"
          body={
            summary && summary.session_count === 1
              ? 'One charge logged. Efficiency needs a second charge to measure the distance between.'
              : 'Log at least two charges and your real-world figures will appear here.'
          }
        />
      </>
    )
  }

  const efficiencySeries = intervals.map(i => ({
    date: shortDate(i.end_date),
    value: i.efficiency_kwh_per_100km,
    exact: i.energy_is_exact,
  }))
  const costSeries = intervals
    .filter(i => i.cost_per_100km != null)
    .map(i => ({ date: shortDate(i.end_date), value: i.cost_per_100km }))

  // Spend by charger type — where the money actually goes.
  const byCharger = new Map<ChargerType, number>()
  sessions.forEach(s => {
    if (s.cost != null) byCharger.set(s.charger_type, (byCharger.get(s.charger_type) ?? 0) + s.cost)
  })
  const chargerSeries = [...byCharger.entries()]
    .map(([type, cost]) => ({ name: CHARGER_LABEL[type], value: Number(cost.toFixed(2)) }))
    .sort((a, b) => b.value - a.value)

  const approximate = intervals.some(i => !i.energy_is_exact)

  return (
    <>
      <PageHeader
        title="Stats"
        subtitle={`${summary.total_distance_km.toLocaleString()} km measured across ${summary.interval_count} interval${summary.interval_count === 1 ? '' : 's'}.`}
      />

      {owned.length > 1 && (
        <div className="mb-4">
          <VehiclePicker vehicles={owned} value={selected!} onChange={setVehicleId} />
        </div>
      )}

      <section aria-label="Summary" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Efficiency"
          value={summary.avg_efficiency_kwh_per_100km != null ? String(summary.avg_efficiency_kwh_per_100km) : '—'}
          unit="kWh/100km"
          hint={summary.energy_is_exact ? 'Measured from battery %' : 'Approximate'}
        />
        <StatTile
          label="Running cost"
          value={summary.avg_cost_per_100km != null ? `€${summary.avg_cost_per_100km.toFixed(2)}` : '—'}
          unit="/100km"
          accent="var(--accent-3)"
        />
        <StatTile
          label="Avg rate"
          value={summary.avg_price_per_kwh != null ? `€${summary.avg_price_per_kwh.toFixed(3)}` : '—'}
          unit="/kWh"
          hint="Blended across chargers"
          accent="var(--accent-2)"
        />
        <StatTile
          label="Total spend"
          value={`€${summary.total_cost.toFixed(2)}`}
          hint={`${summary.total_kwh_added.toFixed(1)} kWh added`}
        />
      </section>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <ChartCard
          title="Efficiency over time"
          subtitle="kWh per 100 km, one point per interval between charges"
          footer={approximate ? 'Hollow points are approximate — battery % was not recorded.' : undefined}
        >
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={efficiencySeries} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="date" {...axisProps} />
              <YAxis {...axisProps} />
              <Tooltip content={<Tip unit="kWh/100km" />} cursor={{ stroke: 'var(--border-strong)' }} />
              <Line
                type="monotone" dataKey="value"
                stroke="var(--series-1)" strokeWidth={2}
                dot={(props: { cx?: number; cy?: number; index?: number }) => {
                  const p = efficiencySeries[props.index ?? 0]
                  return (
                    <circle
                      key={props.index}
                      cx={props.cx} cy={props.cy} r={4}
                      fill={p?.exact ? 'var(--series-1)' : 'var(--surface-solid)'}
                      stroke="var(--series-1)" strokeWidth={2}
                    />
                  )
                }}
                activeDot={{ r: 6 }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Cost per 100 km" subtitle="What each interval of driving cost you">
          {costSeries.length === 0 ? (
            <p className="py-12 text-center text-sm text-ink-3">No costs recorded yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={costSeries} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="date" {...axisProps} />
                <YAxis {...axisProps} />
                <Tooltip content={<Tip unit="€/100km" />} cursor={{ stroke: 'var(--border-strong)' }} />
                <Line
                  type="monotone" dataKey="value"
                  stroke="var(--series-3)" strokeWidth={2}
                  dot={{ r: 4, fill: 'var(--series-3)' }} activeDot={{ r: 6 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      {chargerSeries.length > 0 && (
        <div className="mt-3">
          <ChartCard title="Spend by charger type" subtitle="Where your charging money goes">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={chargerSeries} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="name" {...axisProps} />
                <YAxis {...axisProps} />
                <Tooltip content={<Tip unit="€" />} cursor={{ fill: 'var(--border)' }} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                  {chargerSeries.map((_, i) => (
                    <Cell key={i} fill="var(--series-1)" />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      )}

      <GlassCard className="mt-3">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-sm">
            <caption className="px-4 pt-4 text-left text-sm font-semibold text-ink">
              Interval detail
              <span className="ml-2 font-normal text-xs text-ink-3">
                the same data as the charts, in full
              </span>
            </caption>
            <thead>
              <tr className="border-b border-edge text-left">
                {['Period', 'Distance', 'Energy used', 'kWh/100km', '€/100km', 'Driving'].map(h => (
                  <th key={h} className="px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-ink-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {intervals.map(i => (
                <tr key={`${i.from_session_id}-${i.to_session_id}`} className="border-b border-edge last:border-0">
                  <td className="readout px-4 py-3 text-ink-2">{i.start_date} → {i.end_date}</td>
                  <td className="readout px-4 py-3 text-ink">{i.distance_km.toLocaleString()} km</td>
                  <td className="readout px-4 py-3 text-ink-2">
                    {i.energy_used_kwh} kWh{!i.energy_is_exact && <span className="text-ink-3"> ~</span>}
                  </td>
                  <td className="readout px-4 py-3 font-medium text-ink">{i.efficiency_kwh_per_100km}</td>
                  <td className="readout px-4 py-3 text-ink-2">
                    {i.cost_per_100km != null ? `€${i.cost_per_100km.toFixed(2)}` : '—'}
                  </td>
                  <td className="px-4 py-3 capitalize text-ink-2">{i.driving_mix ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>
    </>
  )
}
