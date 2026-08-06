import { useState } from 'react'
import { getVehicles } from '../api/vehicles'
import { getComparison } from '../api/stats'
import { useAsync } from '../hooks/useAsync'
import PageHeader from '../components/PageHeader'
import GlassCard from '../components/GlassCard'
import StatTile from '../components/StatTile'
import { Field, Select } from '../components/form'
import { Loading, ErrorState, EmptyState } from '../components/States'

const fmt = (n: number, d = 2) =>
  n.toLocaleString('en-IE', { minimumFractionDigits: d, maximumFractionDigits: d })

export default function Compare() {
  const [evId, setEvId] = useState<number | null>(null)
  const [petrolId, setPetrolId] = useState<number | null>(null)

  const { data, error, loading, reload } = useAsync(async () => {
    const vehicles = await getVehicles()
    const owned = vehicles.filter(v => !v.is_comparison_vehicle)
    const petrols = vehicles.filter(
      v => v.is_comparison_vehicle && v.fuel_consumption_l_per_100km != null
    )
    const selectedEv = evId ?? owned[0]?.id ?? null
    const selectedPetrol = petrolId ?? petrols[0]?.id ?? null

    const comparison =
      selectedEv && selectedPetrol ? await getComparison(selectedEv, selectedPetrol) : null

    return { owned, petrols, selectedEv, selectedPetrol, comparison }
  }, [evId, petrolId])

  if (loading) return <Loading label="Pricing your driving both ways…" />
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (!data) return null

  const { owned, petrols, selectedEv, selectedPetrol, comparison } = data

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

  if (!comparison || comparison.distance_km === 0) {
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

  const saved = comparison.saving >= 0
  const priced = comparison.intervals.filter(i => i.petrol_cost != null)

  return (
    <>
      <PageHeader
        title="vs Petrol"
        subtitle={`${comparison.distance_km.toLocaleString()} km of real driving, priced at the pump rates that applied at the time.`}
      />

      <GlassCard className="mb-4 p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Your EV">
            <Select value={selectedEv ?? ''} onChange={e => setEvId(Number(e.target.value))}>
              {owned.map(v => (
                <option key={v.id} value={v.id}>{v.nickname || `${v.make} ${v.model}`}</option>
              ))}
            </Select>
          </Field>
          <Field label="Compared to">
            <Select value={selectedPetrol ?? ''} onChange={e => setPetrolId(Number(e.target.value))}>
              {petrols.map(v => (
                <option key={v.id} value={v.id}>
                  {v.make} {v.model} — {v.fuel_consumption_l_per_100km} L/100km
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <p className="mt-3 text-xs text-ink-3">
          Petrol prices come from the EU Weekly Oil Bulletin (Irish national average, updated
          weekly). Add your own prices to override them for a date or city.
        </p>
      </GlassCard>

      {comparison.unpriced_intervals > 0 && (
        <GlassCard className="mb-4 p-4">
          <div className="flex items-start gap-2.5">
            <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" strokeWidth="2" strokeLinecap="round" className="mt-0.5 shrink-0">
              <path d="M12 9v4M12 17v.01M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6A2 2 0 0 0 22 18L13.7 3.9a2 2 0 0 0-3.4 0z" />
            </svg>
            <p className="text-sm text-ink-2">
              {comparison.unpriced_intervals} interval
              {comparison.unpriced_intervals === 1 ? ' has' : 's have'} no petrol price for that
              date, so {comparison.unpriced_intervals === 1 ? 'it is' : 'they are'} left out of the
              total. Import the Oil Bulletin from the API, or add prices manually.
            </p>
          </div>
        </GlassCard>
      )}

      <section aria-label="Cost comparison" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="You paid" value={`€${fmt(comparison.ev_cost)}`} hint="Charging" />
        <StatTile
          label="Petrol would cost"
          value={`€${fmt(comparison.petrol_cost)}`}
          hint={`${fmt(comparison.litres, 1)} litres`}
          accent="var(--series-2)"
        />
        <StatTile
          label="EV per 100km"
          value={comparison.ev_cost_per_100km != null ? `€${fmt(comparison.ev_cost_per_100km)}` : '—'}
          accent="var(--accent-3)"
        />
        <StatTile
          label="Petrol per 100km"
          value={comparison.petrol_cost_per_100km != null ? `€${fmt(comparison.petrol_cost_per_100km)}` : '—'}
          accent="var(--series-2)"
        />
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
            <p className="readout mt-1 text-3xl font-semibold text-ink">
              €{fmt(Math.abs(comparison.saving))}
            </p>
            <p className="mt-1 text-sm text-ink-2">
              {saved ? 'saved' : 'extra'} over {comparison.distance_km.toLocaleString()} km
              {comparison.petrol_cost > 0 &&
                ` · ${fmt(Math.abs(comparison.saving / comparison.petrol_cost) * 100, 0)}% ${saved ? 'less' : 'more'}`}
            </p>
            <p className="mt-3 text-xs text-ink-3">
              Against a {comparison.comparison_vehicle} at {comparison.l_per_100km} L/100km. The
              first charge is excluded — it paid for driving from before you started logging.
            </p>
          </div>
        </div>
      </GlassCard>

      {priced.length > 0 && (
        <GlassCard className="mt-3">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[44rem] text-sm">
              <caption className="px-4 pt-4 text-left text-sm font-semibold text-ink">
                Priced interval by interval
                <span className="ml-2 text-xs font-normal text-ink-3">
                  each stretch at the pump price of the week it ended
                </span>
              </caption>
              <thead>
                <tr className="border-b border-edge text-left">
                  {['Period', 'Distance', 'Litres', 'Price/L', 'Priced as of', 'Petrol cost'].map(h => (
                    <th key={h} className="px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-ink-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparison.intervals.map(i => (
                  <tr key={`${i.start_date}-${i.end_date}`} className="border-b border-edge last:border-0">
                    <td className="readout px-4 py-3 text-ink-2">{i.start_date} → {i.end_date}</td>
                    <td className="readout px-4 py-3 text-ink">{i.distance_km.toLocaleString()} km</td>
                    <td className="readout px-4 py-3 text-ink-2">{fmt(i.litres, 1)}</td>
                    <td className="readout px-4 py-3 text-ink">
                      {i.price_per_litre != null ? `€${fmt(i.price_per_litre, 3)}` : '—'}
                    </td>
                    <td className="readout px-4 py-3 text-ink-3">{i.price_as_of ?? '—'}</td>
                    <td className="readout px-4 py-3 font-medium text-ink">
                      {i.petrol_cost != null ? `€${fmt(i.petrol_cost)}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}
    </>
  )
}
