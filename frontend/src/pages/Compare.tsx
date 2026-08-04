import { useState } from 'react'
import { getVehicles } from '../api/vehicles'
import { getSummary } from '../api/stats'
import { useAsync } from '../hooks/useAsync'
import PageHeader from '../components/PageHeader'
import GlassCard from '../components/GlassCard'
import StatTile from '../components/StatTile'
import { Field, TextInput, Select } from '../components/form'
import { Loading, ErrorState, EmptyState } from '../components/States'

// Placeholder until a live Irish fuel-price feed is wired in.
const DEFAULT_PETROL_PRICE = 1.79

const fmt = (n: number, d = 2) =>
  n.toLocaleString('en-IE', { minimumFractionDigits: d, maximumFractionDigits: d })

export default function Compare() {
  const [pricePerLitre, setPricePerLitre] = useState(DEFAULT_PETROL_PRICE)
  const [evId, setEvId] = useState<number | null>(null)
  const [petrolId, setPetrolId] = useState<number | null>(null)

  const { data, error, loading, reload } = useAsync(async () => {
    const vehicles = await getVehicles()
    const owned = vehicles.filter(v => !v.is_comparison_vehicle)
    const petrols = vehicles.filter(
      v => v.is_comparison_vehicle && v.fuel_consumption_l_per_100km != null
    )
    const selectedEv = evId ?? owned[0]?.id ?? null
    const summary = selectedEv ? await getSummary(selectedEv) : null
    return { owned, petrols, selectedEv, summary }
  }, [evId])

  if (loading) return <Loading label="Working out the difference…" />
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (!data) return null

  const { owned, petrols, selectedEv, summary } = data
  const ev = owned.find(v => v.id === selectedEv)

  if (owned.length === 0) {
    return (
      <>
        <PageHeader title="vs Petrol" subtitle="What the same driving would have cost in petrol." />
        <EmptyState title="Add your EV first" body="Then add a petrol car to compare it against." />
      </>
    )
  }

  if (petrols.length === 0) {
    return (
      <>
        <PageHeader title="vs Petrol" subtitle="What the same driving would have cost in petrol." />
        <EmptyState
          title="No comparison car set up"
          body="In the Garage, add a petrol car with a consumption figure (L/100km) and tick “Comparison car”."
        />
      </>
    )
  }

  const petrol = petrols.find(v => v.id === petrolId) ?? petrols[0]
  const lPer100 = petrol.fuel_consumption_l_per_100km!

  const distance = summary?.total_distance_km ?? 0
  if (!summary || distance === 0) {
    return (
      <>
        <PageHeader title="vs Petrol" subtitle="What the same driving would have cost in petrol." />
        <EmptyState
          title="Not enough data yet"
          body="Log at least two charges so there's a measured distance to price up."
        />
      </>
    )
  }

  // Only the cost attributed to measured intervals is comparable, since that is
  // the same driving the petrol figure is priced against.
  const evCost = (summary.avg_cost_per_100km ?? 0) / 100 * distance
  const petrolCost = distance / 100 * lPer100 * pricePerLitre
  const litres = distance / 100 * lPer100
  const saving = petrolCost - evCost
  const saved = saving >= 0

  return (
    <>
      <PageHeader
        title="vs Petrol"
        subtitle={`${distance.toLocaleString()} km of real driving, priced both ways.`}
      />

      <GlassCard className="mb-4 p-5">
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Your EV">
            <Select value={selectedEv ?? ''} onChange={e => setEvId(Number(e.target.value))}>
              {owned.map(v => (
                <option key={v.id} value={v.id}>{v.nickname || `${v.make} ${v.model}`}</option>
              ))}
            </Select>
          </Field>
          <Field label="Compared to">
            <Select value={petrol.id} onChange={e => setPetrolId(Number(e.target.value))}>
              {petrols.map(v => (
                <option key={v.id} value={v.id}>
                  {v.make} {v.model} — {v.fuel_consumption_l_per_100km} L/100km
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Petrol price (€/litre)" hint="Manual for now — a live feed is on the roadmap">
            <TextInput
              type="number" step="0.01" min="0"
              value={pricePerLitre}
              onChange={e => setPricePerLitre(Number(e.target.value) || 0)}
            />
          </Field>
        </div>
      </GlassCard>

      <section aria-label="Cost comparison" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="You paid" value={`€${fmt(evCost)}`} hint={ev ? ev.nickname || `${ev.make} ${ev.model}` : 'Charging'} />
        <StatTile label="Petrol would cost" value={`€${fmt(petrolCost)}`} hint={`${fmt(litres, 1)} litres`} accent="var(--series-2)" />
        <StatTile label="EV per 100km" value={`€${fmt(summary.avg_cost_per_100km ?? 0)}`} accent="var(--accent-3)" />
        <StatTile label="Petrol per 100km" value={`€${fmt(lPer100 * pricePerLitre)}`} accent="var(--series-2)" />
      </section>

      <GlassCard className="mt-4 p-6">
        <div className="flex items-start gap-3">
          {/* icon + label, so the status colour never carries the meaning alone */}
          <svg
            aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none"
            stroke={saved ? 'var(--good)' : 'var(--critical)'}
            strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 shrink-0"
          >
            {saved ? <path d="M12 19V5M5 12l7-7 7 7" /> : <path d="M12 5v14M19 12l-7 7-7-7" />}
          </svg>
          <div>
            <p className="text-sm font-medium text-ink">
              {saved ? 'Cheaper to drive electric' : 'Petrol would have been cheaper'}
            </p>
            <p className="readout mt-1 text-3xl font-semibold text-ink">€{fmt(Math.abs(saving))}</p>
            <p className="mt-1 text-sm text-ink-2">
              {saved ? 'saved' : 'extra'} over {distance.toLocaleString()} km
              {petrolCost > 0 && ` · ${fmt(Math.abs(saving / petrolCost) * 100, 0)}% ${saved ? 'less' : 'more'}`}
            </p>
            <p className="mt-3 text-xs text-ink-3">
              Based on charges logged against measured distance. The first charge is excluded — it
              paid for driving from before you started logging.
            </p>
          </div>
        </div>
      </GlassCard>
    </>
  )
}
