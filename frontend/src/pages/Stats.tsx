import { useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Cell,
} from 'recharts'
import { getVehicles } from '../api/vehicles'
import { getIntervals, getSummary } from '../api/stats'
import { getFuelEvents } from '../api/fuelEvents'
import { CHARGER_LABEL, type ChargerType } from '../types'
import { eventNoun, takesElectricity } from '../fuel'
import { useAsync } from '../hooks/useAsync'
import { useUnits } from '../hooks/useUnits'
import { useCurrency } from '../hooks/useCurrency'
import PageHeader from '../components/PageHeader'
import GlassCard from '../components/GlassCard'
import StatTile from '../components/StatTile'
import VehiclePicker from '../components/VehiclePicker'
import { ChartCard, Tip, axisProps, gridProps } from '../components/charts'
import { Loading, ErrorState, EmptyState } from '../components/States'

const fmtCo2 = (n: number) =>
  n.toLocaleString('en-IE', { maximumFractionDigits: n < 10 ? 1 : 0 })

const shortDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-IE', { day: 'numeric', month: 'short' })

export default function Stats() {
  const { units } = useUnits()
  const money = useCurrency()
  const [vehicleId, setVehicleId] = useState<number | null>(null)

  const { data, error, loading, reload } = useAsync(async () => {
    const vehicles = await getVehicles()
    const owned = vehicles.filter(v => v.is_owned)
    const selected = vehicleId ?? owned[0]?.id ?? null
    if (!selected) return { owned, selected, summary: null, intervals: [], events: [] }
    const [summary, iv, sessions] = await Promise.all([
      getSummary(selected),
      getIntervals(selected),
      getFuelEvents(selected),
    ])
    return { owned, selected, summary, intervals: iv.intervals, events: sessions }
  }, [vehicleId])

  if (loading) return <Loading label="Crunching your numbers…" />
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (!data) return null

  const { owned, selected, summary, intervals, events } = data
  // Wording and units follow the car being looked at, not the app's origins.
  const vehicle = owned.find(v => v.id === selected) ?? owned[0]
  const fuel = vehicle?.fuel_type ?? 'electric'
  const electric = takesElectricity(fuel)
  const noun = eventNoun(fuel)

  if (owned.length === 0) {
    return (
      <>
        <PageHeader title="Stats" subtitle="What your car actually costs to run." />
        <EmptyState title="Add a vehicle first" body="Stats appear once you have a car and a couple of charges logged." />
      </>
    )
  }

  if (!summary || summary.interval_count === 0) {
    return (
      <>
        <PageHeader title="Stats" subtitle="What your car actually costs to run." />
        {owned.length > 1 && (
          <div className="mb-4">
            <VehiclePicker vehicles={owned} value={selected!} onChange={setVehicleId} />
          </div>
        )}
        <EmptyState
          title="Not enough data yet"
          body={
            summary && summary.event_count === 1
              ? `One ${noun} logged. A consumption figure needs a second one to measure the distance between.`
              : `Log at least two ${eventNoun(fuel, true)} and your real-world figures will appear here.`
          }
        />
      </>
    )
  }

  const consumptionOf = (i: (typeof intervals)[number]) =>
    electric ? i.efficiency_kwh_per_100km : i.consumption_l_per_100km
  const exactOf = (i: (typeof intervals)[number]) =>
    electric ? i.energy_is_exact : i.volume_is_exact
  const format = electric ? units.efficiency : units.consumption
  const consumptionUnit = electric ? units.efficiencyUnit : units.consumptionUnit

  const efficiencySeries = intervals.map(i => ({
    date: shortDate(i.end_date),
    value:
      consumptionOf(i) == null ? null : Number(format(consumptionOf(i)).replace(/,/g, '')),
    exact: exactOf(i),
  }))
  const costSeries = intervals
    .filter(i => i.cost_per_100km != null)
    .map(i => ({
      date: shortDate(i.end_date),
      value:
        units.system === 'imperial'
          ? Number((i.cost_per_100km! / 62.1371).toFixed(3))
          : i.cost_per_100km,
    }))

  // Spend by charger type — where the money actually goes.
  const byCharger = new Map<ChargerType, number>()
  events.forEach(e => {
    if (e.cost != null && e.charger_type)
      byCharger.set(e.charger_type, (byCharger.get(e.charger_type) ?? 0) + e.cost)
  })
  const chargerSeries = [...byCharger.entries()]
    .map(([type, cost]) => ({ name: CHARGER_LABEL[type], value: Number(cost.toFixed(2)) }))
    .sort((a, b) => b.value - a.value)

  const approximate = intervals.some(i => consumptionOf(i) != null && !exactOf(i))

  return (
    <>
      <PageHeader
        title="Stats"
        subtitle={`${units.distance(summary.total_distance_km)} measured across ${summary.interval_count} interval${summary.interval_count === 1 ? '' : 's'}.`}
      />

      {owned.length > 1 && (
        <div className="mb-4">
          <VehiclePicker vehicles={owned} value={selected!} onChange={setVehicleId} />
        </div>
      )}

      <section aria-label="Summary" className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatTile
          label={electric ? 'Efficiency' : 'Consumption'}
          value={format(
            electric ? summary.avg_efficiency_kwh_per_100km : summary.avg_consumption_l_per_100km,
          )}
          unit={consumptionUnit}
          hint={
            (electric ? summary.energy_is_exact : summary.volume_is_exact)
              ? `Measured from ${electric ? 'battery' : 'fuel'} %`
              : 'Approximate'
          }
        />
        <StatTile
          label="Running cost"
          unit={units.costUnit}
          value={money.format(units.costPerDistanceAmount(summary.avg_cost_per_100km), units.costDigits)}
          accent="var(--accent-3)"
        />
        <StatTile
          label="Avg rate"
          value={
            electric
              ? summary.avg_price_per_kwh != null
                ? money.format(summary.avg_price_per_kwh, 3)
                : '—'
              : summary.avg_price_per_litre != null
                ? money.format(summary.avg_price_per_litre, 3)
                : '—'
          }
          unit={electric ? '/kWh' : '/L'}
          hint={electric ? 'Blended across chargers' : 'Blended across fill-ups'}
          accent="var(--accent-2)"
        />
        <StatTile
          label="CO2"
          value={
            summary.avg_co2_g_per_km != null ? fmtCo2(summary.avg_co2_g_per_km) : '—'
          }
          unit="g/km"
          hint={
            summary.total_co2_kg != null
              ? `${fmtCo2(summary.total_co2_kg)} kg so far`
              : 'Needs a measured interval'
          }
          accent="var(--series-2)"
        />
        <StatTile
          label="Total spend"
          value={money.format(summary.total_cost)}
          hint={
            electric
              ? `${summary.total_energy_added_kwh.toFixed(1)} kWh added`
              : `${summary.total_volume_added_litres.toFixed(1)} L added`
          }
        />
      </section>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <ChartCard
          title={`${electric ? 'Efficiency' : 'Consumption'} over time`}
          subtitle={`${consumptionUnit}, one point per interval between ${eventNoun(fuel, true)}`}
          footer={
            approximate
              ? `Hollow points are approximate — the ${electric ? 'battery' : 'fuel'} % was not recorded.`
              : undefined
          }
        >
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={efficiencySeries} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="date" {...axisProps} />
              <YAxis {...axisProps} />
              <Tooltip content={<Tip unit={consumptionUnit} />} cursor={{ stroke: 'var(--border-strong)' }} />
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

        <ChartCard
          title={units.system === 'imperial' ? 'Cost per mile' : 'Cost per 100 km'}
          subtitle="What each interval of driving cost you"
        >
          {costSeries.length === 0 ? (
            <p className="py-12 text-center text-sm text-ink-3">No costs recorded yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={costSeries} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="date" {...axisProps} />
                <YAxis {...axisProps} />
                <Tooltip content={<Tip unit={units.system === 'imperial' ? '€/mi' : '€/100km'} />} cursor={{ stroke: 'var(--border-strong)' }} />
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
                {['Period', 'Distance', electric ? 'Energy used' : 'Fuel used', consumptionUnit,
                  'g CO2/km', units.system === 'imperial' ? '€/mi' : '€/100km',
                  'Driving'].map(h => (
                  <th key={h} className="px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-ink-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {intervals.map(i => (
                <tr key={`${i.from_event_id}-${i.to_event_id}`} className="border-b border-edge last:border-0">
                  <td className="readout px-4 py-3 text-ink-2">{i.start_date} → {i.end_date}</td>
                  <td className="readout px-4 py-3 text-ink">{units.distance(i.distance_km)}</td>
                  <td className="readout px-4 py-3 text-ink-2">
                    {electric ? `${i.energy_used_kwh} kWh` : `${i.volume_used_litres} L`}
                    {!exactOf(i) && <span className="text-ink-3"> ~</span>}
                  </td>
                  <td className="readout px-4 py-3 font-medium text-ink">{format(consumptionOf(i))}</td>
                  <td className="readout px-4 py-3 text-ink-2">
                    {i.co2_g_per_km != null ? fmtCo2(i.co2_g_per_km) : '—'}
                  </td>
                  <td className="readout px-4 py-3 text-ink-2">
                    {units.costPerDistance(i.cost_per_100km, (v, d) => money.format(v, d))}
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
