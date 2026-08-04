import { useState } from 'react'
import { getVehicles } from '../api/vehicles'
import { getTrips } from '../api/trips'
import { getChargingSessions } from '../api/charging'
import { useAsync } from '../hooks/useAsync'
import PageHeader from '../components/PageHeader'
import GlassCard from '../components/GlassCard'
import StatTile from '../components/StatTile'
import { Loading, ErrorState, EmptyState } from '../components/States'

// Placeholder until a fuel-price API is wired in; roughly Irish unleaded.
const DEFAULT_PETROL_PRICE = 1.79

const fmt = (n: number, d = 2) =>
  n.toLocaleString('en-IE', { minimumFractionDigits: d, maximumFractionDigits: d })

export default function Compare() {
  const [pricePerLitre, setPricePerLitre] = useState(DEFAULT_PETROL_PRICE)
  const [comparisonId, setComparisonId] = useState<number | null>(null)

  const { data, error, loading, reload } = useAsync(
    () => Promise.all([getVehicles(), getTrips(), getChargingSessions()]),
    []
  )

  if (loading) return <Loading label="Crunching the comparison…" />
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (!data) return null

  const [vehicles, trips, sessions] = data
  const comparisons = vehicles.filter(v => v.is_comparison_vehicle && v.fuel_consumption_l_per_100km != null)

  if (comparisons.length === 0) {
    return (
      <>
        <PageHeader title="EV vs Petrol" subtitle="What the same driving would have cost in petrol." />
        <EmptyState
          title="No comparison car set up"
          body="Add a petrol vehicle with a fuel consumption figure (L/100km) and mark it as a comparison vehicle."
        />
      </>
    )
  }

  const selected = comparisons.find(v => v.id === comparisonId) ?? comparisons[0]
  const lPer100 = selected.fuel_consumption_l_per_100km!

  const totalKm = trips.reduce((s, t) => s + t.distance_km, 0)
  const evCost = sessions.reduce((s, c) => s + (c.cost ?? 0), 0)
  const petrolCost = (totalKm / 100) * lPer100 * pricePerLitre
  const saving = petrolCost - evCost
  const litres = (totalKm / 100) * lPer100

  if (totalKm === 0) {
    return (
      <>
        <PageHeader title="EV vs Petrol" subtitle="What the same driving would have cost in petrol." />
        <EmptyState title="No trips logged yet" body="Log some trips and charging sessions to see the comparison." />
      </>
    )
  }

  const saved = saving >= 0

  return (
    <>
      <PageHeader
        title="EV vs Petrol"
        subtitle={`${totalKm.toFixed(0)} km driven, priced against a ${selected.make} ${selected.model}.`}
      />

      <GlassCard className="mb-4 p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-[11px] uppercase tracking-wider text-ink-3">Comparison car</span>
            <select
              value={selected.id}
              onChange={e => setComparisonId(Number(e.target.value))}
              className="focus-ring mt-1.5 w-full rounded-lg border border-edge bg-surface-solid px-3 py-2 text-sm text-ink"
            >
              {comparisons.map(v => (
                <option key={v.id} value={v.id}>
                  {v.make} {v.model} — {v.fuel_consumption_l_per_100km} L/100km
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-[11px] uppercase tracking-wider text-ink-3">Petrol price (€/litre)</span>
            <input
              type="number"
              step="0.01"
              min="0"
              value={pricePerLitre}
              onChange={e => setPricePerLitre(Number(e.target.value) || 0)}
              className="readout focus-ring mt-1.5 w-full rounded-lg border border-edge bg-surface-solid px-3 py-2 text-sm text-ink"
            />
          </label>
        </div>
        <p className="mt-3 text-xs text-ink-3">
          Price is entered manually for now — a live Irish fuel-price feed is on the roadmap.
        </p>
      </GlassCard>

      <section aria-label="Cost comparison" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="You paid (EV)" value={`€${fmt(evCost)}`} hint="Actual charging cost" />
        <StatTile
          label="Petrol would cost"
          value={`€${fmt(petrolCost)}`}
          hint={`${fmt(litres, 1)} litres`}
          accent="var(--series-2)"
        />
        <StatTile
          label="EV per 100km"
          value={`€${fmt((evCost / totalKm) * 100)}`}
          accent="var(--accent-2)"
        />
        <StatTile
          label="Petrol per 100km"
          value={`€${fmt(lPer100 * pricePerLitre)}`}
          accent="var(--series-2)"
        />
      </section>

      <GlassCard className="mt-4 p-6">
        <div className="flex items-start gap-3">
          {/* icon + label, so the status colour never carries the meaning alone */}
          <svg
            aria-hidden="true"
            width="20" height="20" viewBox="0 0 24 24" fill="none"
            stroke={saved ? 'var(--good)' : 'var(--critical)'}
            strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            className="mt-0.5 shrink-0"
          >
            {saved ? <path d="M12 19V5M5 12l7-7 7 7" /> : <path d="M12 5v14M19 12l-7 7-7-7" />}
          </svg>
          <div>
            <p className="text-sm font-medium text-ink">
              {saved ? 'Cheaper to drive electric' : 'Petrol would have been cheaper'}
            </p>
            <p className="readout mt-1 text-3xl font-semibold text-ink">
              €{fmt(Math.abs(saving))}
            </p>
            <p className="mt-1 text-sm text-ink-2">
              {saved ? 'saved' : 'extra'} over {totalKm.toFixed(0)} km
              {petrolCost > 0 && ` · ${fmt(Math.abs(saving / petrolCost) * 100, 0)}% ${saved ? 'less' : 'more'}`}
            </p>
          </div>
        </div>
      </GlassCard>
    </>
  )
}
