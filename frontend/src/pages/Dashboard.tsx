import { getTrips } from '../api/trips'
import { getChargingSessions } from '../api/charging'
import { getVehicles } from '../api/vehicles'
import { useAsync } from '../hooks/useAsync'
import PageHeader from '../components/PageHeader'
import StatTile from '../components/StatTile'
import GlassCard from '../components/GlassCard'
import { Loading, ErrorState, EmptyState } from '../components/States'

const fmt = (n: number, digits = 1) =>
  n.toLocaleString('en-IE', { minimumFractionDigits: digits, maximumFractionDigits: digits })

export default function Dashboard() {
  const { data, error, loading, reload } = useAsync(
    () => Promise.all([getVehicles(), getTrips(), getChargingSessions()]),
    []
  )

  if (loading) return <Loading label="Loading your data…" />
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (!data) return null

  const [vehicles, trips, sessions] = data
  const evs = vehicles.filter(v => !v.is_comparison_vehicle)

  const totalKm = trips.reduce((s, t) => s + t.distance_km, 0)
  const totalKwh = sessions.reduce((s, c) => s + c.kwh_charged, 0)
  const totalCost = sessions.reduce((s, c) => s + (c.cost ?? 0), 0)

  // Only meaningful once there is data on both sides.
  const kwhPer100 = totalKm > 0 ? (totalKwh / totalKm) * 100 : null
  const costPer100 = totalKm > 0 ? (totalCost / totalKm) * 100 : null
  const pricePerKwh = totalKwh > 0 ? totalCost / totalKwh : null

  if (vehicles.length === 0) {
    return (
      <>
        <PageHeader title="Dashboard" subtitle="Your real-world EV running costs." />
        <EmptyState
          title="No vehicles yet"
          body="Add your EV to start logging trips and charging sessions."
        />
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle={
          evs.length
            ? `Real-world figures for your ${evs.map(v => `${v.make} ${v.model}`).join(', ')}.`
            : 'Real-world running costs.'
        }
      />

      <section aria-label="Summary" className="grid grid-cols-2 gap-3 lg:grid-cols-3">
        <StatTile label="Distance" value={fmt(totalKm, 0)} unit="km" hint={`${trips.length} trip${trips.length === 1 ? '' : 's'} logged`} />
        <StatTile label="Energy" value={fmt(totalKwh)} unit="kWh" hint={`${sessions.length} charge${sessions.length === 1 ? '' : 's'}`} accent="var(--accent-2)" />
        <StatTile label="Spend" value={`€${fmt(totalCost, 2)}`} hint="Total charging cost" accent="var(--accent-3)" />
        <StatTile
          label="Efficiency"
          value={kwhPer100 ? fmt(kwhPer100) : '—'}
          unit={kwhPer100 ? 'kWh/100km' : undefined}
          hint={kwhPer100 ? 'Your actual consumption' : 'Needs a trip and a charge'}
        />
        <StatTile
          label="Running cost"
          value={costPer100 ? `€${fmt(costPer100, 2)}` : '—'}
          unit={costPer100 ? '/100km' : undefined}
          hint={costPer100 ? 'What driving actually costs' : 'Needs a trip and a charge'}
          accent="var(--accent-2)"
        />
        <StatTile
          label="Avg rate"
          value={pricePerKwh ? `€${fmt(pricePerKwh, 3)}` : '—'}
          unit={pricePerKwh ? '/kWh' : undefined}
          hint="Blended across chargers"
          accent="var(--accent-3)"
        />
      </section>

      {trips.length === 0 && (
        <GlassCard className="mt-4 p-5">
          <p className="text-sm text-ink-2">
            Log a trip and a charging session to unlock efficiency and cost-per-km figures — those
            are the numbers WLTP estimates can’t tell you.
          </p>
        </GlassCard>
      )}
    </>
  )
}
