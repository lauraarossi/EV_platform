import { useState } from 'react'
import { getVehicles } from '../api/vehicles'
import { getComparison, getSummary } from '../api/stats'
import { FUEL_LABEL, eventNoun, takesElectricity } from '../fuel'
import { useAsync } from '../hooks/useAsync'
import { useDebounced } from '../hooks/useDebounced'
import { useUnits } from '../hooks/useUnits'
import PageHeader from '../components/PageHeader'
import GlassCard from '../components/GlassCard'
import StatTile from '../components/StatTile'
import { Field, Select } from '../components/form'
import { Loading, ErrorState, EmptyState } from '../components/States'

const fmt = (n: number, d = 2) =>
  n.toLocaleString('en-IE', { minimumFractionDigits: d, maximumFractionDigits: d })

const SUBTITLE = 'What the same driving would have cost in a different car.'

/**
 * Comparing running costs in either direction.
 *
 * Nothing here assumes which side is electric: an EV owner pricing petrol and
 * a diesel owner pricing an EV are the same question asked from opposite ends,
 * and the API answers both the same way.
 */
export default function Compare() {
  const { units } = useUnits()
  const [mineId, setMineId] = useState<number | null>(null)
  const [otherId, setOtherId] = useState<number | null>(null)
  // How far your car's consumption sits from the figure you entered towards
  // the one your log shows. Debounced so dragging is one request, not fifty.
  const [weight, setWeight] = useState(0)
  const settledWeight = useDebounced(weight, 250)
  // Null means "use the first car's logged history". A number is a distance
  // typed in, which is the only way two Showroom cars can be compared at all.
  const [distance, setDistance] = useState<number | null>(null)
  const settledDistance = useDebounced(distance, 400)

  const { data, error, loading, reload } = useAsync(async () => {
    const vehicles = await getVehicles()
    // Either side can be any car — two from the Garage, two from the Showroom,
    // or one of each. The only requirement is the consumption figure the whole
    // estimate rests on, and that the two are not the same car.
    const comparable = (v: (typeof vehicles)[number]) =>
      v.fuel_consumption_l_per_100km != null ||
      v.consumption_kwh_per_100km != null ||
      (v.battery_capacity_kwh != null && v.wltp_range_km != null)

    const candidates = vehicles.filter(comparable)
    const selectedMine = mineId ?? candidates[0]?.id ?? null
    const alternatives = candidates.filter(v => v.id !== selectedMine)
    const selectedOther = otherId ?? alternatives[0]?.id ?? null

    // Only a car with a log offers a distance of its own to compare over.
    const summary = selectedMine ? await getSummary(selectedMine).catch(() => null) : null
    const loggedKm = summary?.total_distance_km ?? 0
    // Typed in whatever unit is on display; the API deals only in km.
    const entered = settledDistance ?? (loggedKm > 0 ? null : 10_000)
    const useDistance = entered != null ? units.toKm(entered) : undefined

    const comparison =
      selectedMine && selectedOther
        ? await getComparison(
            selectedMine, selectedOther, undefined, settledWeight, useDistance,
          ).catch(() => null)
        : null

    return { candidates, alternatives, selectedMine, selectedOther, comparison, loggedKm }
  }, [mineId, otherId, settledWeight, settledDistance, units.system])

  if (loading) return <Loading label="Pricing your driving both ways…" />
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (!data) return null

  const { candidates, alternatives, selectedMine, selectedOther, comparison, loggedKm } = data

  if (candidates.length < 2) {
    return (
      <>
        <PageHeader title="Compare" subtitle={SUBTITLE} />
        <EmptyState
          title={candidates.length === 0 ? 'Nothing to compare yet' : 'One car isn’t a comparison'}
          body="Any two cars will do — both from the Garage, both from the Showroom, or one of each. Each needs a consumption figure: L/100km for petrol or diesel, kWh/100km for an electric one."
        />
      </>
    )
  }

  const mine = candidates.find(v => v.id === selectedMine) ?? candidates[0]

  if (!comparison || comparison.distance_km === 0) {
    return (
      <>
        <PageHeader title="Compare" subtitle={SUBTITLE} />
        <EmptyState
          title="Not enough data yet"
          body={`Log at least two ${eventNoun(mine.fuel_type, true)} so there's a measured distance to price up.`}
        />
      </>
    )
  }

  const ahead = comparison.saving >= 0
  const cleaner = comparison.co2_saving_kg >= 0
  const yourName = mine.nickname || `${mine.make} ${mine.model}`
  const theirName = comparison.comparison_vehicle
  const yourUnitLabel = mine.fuel_type === 'electric' ? 'kWh' : 'L'
  const sameFuel = mine.fuel_type === comparison.comparison_fuel
  const electricityInvolved =
    takesElectricity(mine.fuel_type) || takesElectricity(comparison.comparison_fuel)
  const priced = comparison.intervals.filter(i => i.cost != null)
  const otherIsElectric = takesElectricity(comparison.comparison_fuel)
  const otherFuel = FUEL_LABEL[comparison.comparison_fuel]
  const priceNoun = otherIsElectric ? 'electricity rate' : 'pump price'

  return (
    <>
      <PageHeader
        title="Compare"
        subtitle={`${units.distance(comparison.distance_km)} of your real driving, costed in both cars at the rates that applied at the time.`}
      />

      <GlassCard className="mb-4 p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="First car">
            <Select value={selectedMine ?? ''} onChange={e => setMineId(Number(e.target.value))}>
              {candidates.map(v => (
                <option key={v.id} value={v.id}>
                  {v.nickname || `${v.make} ${v.model}`} — {FUEL_LABEL[v.fuel_type]}
                  {v.is_owned ? ' · Garage' : ' · Showroom'}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Second car">
            <Select value={selectedOther ?? ''} onChange={e => setOtherId(Number(e.target.value))}>
              {alternatives.map(v => (
                <option key={v.id} value={v.id}>
                  {v.nickname || `${v.make} ${v.model}`} — {FUEL_LABEL[v.fuel_type]}
                  {v.is_owned ? ' · Garage' : ' · Showroom'}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="mt-4 border-t border-edge pt-4">
          <p className="text-[11px] uppercase tracking-wider text-ink-3">Compared over</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {loggedKm > 0 && (
              <button
                type="button"
                onClick={() => setDistance(null)}
                aria-pressed={distance === null}
                className="focus-ring rounded-lg px-3 py-1.5 text-xs font-medium"
                style={
                  distance === null
                    ? {
                        background: 'color-mix(in oklab, var(--accent) 18%, transparent)',
                        border: '1px solid color-mix(in oklab, var(--accent) 35%, transparent)',
                        color: 'var(--ink)',
                      }
                    : { border: '1px solid var(--border)', color: 'var(--ink-3)' }
                }
              >
                {mine.nickname || mine.model}'s log ({units.distance(loggedKm)})
              </button>
            )}
            <label className="flex items-center gap-2 text-xs text-ink-3">
              <span>{loggedKm > 0 ? 'or' : 'Distance'}</span>
              <input
                type="number" min={1} step={100}
                value={distance ?? ''}
                placeholder="10000"
                onChange={e => setDistance(e.target.value === '' ? null : Number(e.target.value))}
                className="focus-ring w-28 rounded-lg border border-edge bg-transparent px-2 py-1.5 text-sm text-ink"
              />
              <span>{units.distanceUnit}</span>
            </label>
          </div>
          {loggedKm === 0 && (
            <p className="mt-2 text-xs text-ink-3">
              Neither car has anything logged, so there is no history to measure — pick a
              distance and both are costed over it at today's rates.
            </p>
          )}
        </div>

        {comparison.your_basis_measured != null && (
          <div className="mt-4 border-t border-edge pt-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <label htmlFor="basis" className="text-[11px] uppercase tracking-wider text-ink-3">
                {yourName}'s consumption
              </label>
              <span className="readout text-sm font-medium text-ink">
                {comparison.your_basis} {comparison.basis_label}
              </span>
            </div>

            <input
              id="basis"
              type="range" min={0} max={100} step={5}
              value={Math.round(weight * 100)}
              onChange={e => setWeight(Number(e.target.value) / 100)}
              className="focus-ring mt-3 w-full accent-[var(--accent)]"
            />

            <div className="mt-1 flex justify-between text-xs text-ink-3">
              <button
                type="button" onClick={() => setWeight(0)}
                className="focus-ring rounded px-1 hover:text-ink"
              >
                As entered ({comparison.your_basis_quoted})
              </button>
              <button
                type="button" onClick={() => setWeight(1)}
                className="focus-ring rounded px-1 hover:text-ink"
              >
                As measured ({comparison.your_basis_measured})
              </button>
            </div>

            <p className="mt-2 text-xs text-ink-3">
              {weight === 0 ? (
                <>
                  Both cars on their entered figures, which is the only way the answer is
                  strictly about the cars — enter the same figure twice and the difference is
                  zero.
                </>
              ) : (
                <>
                  <span style={{ color: 'var(--warning)' }}>Not like-for-like:</span> yours is
                  judged {weight === 1 ? 'entirely' : 'partly'} on your real driving while the{' '}
                  {theirName} is still on its quoted figure, which flatters it by whatever your
                  own car falls short by.
                </>
              )}
            </p>
          </div>
        )}

        <p className="mt-3 text-xs text-ink-3">
          {sameFuel
            ? `Both cars run on the same thing, so both are priced at what you actually paid per ${comparison.unit_label} — your receipts beat any national average.`
            : otherIsElectric
              ? 'Yours is priced at what you actually paid. The electric one uses your saved tariff for each date, at its cheapest band — a car you don’t own has no charging history to say when it would have been plugged in.'
              : 'Yours is priced at what you actually paid. The other uses the EU Weekly Oil Bulletin (Irish national average, weekly), which your own entered prices override.'}
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
              {comparison.unpriced_intervals === 1 ? ' has' : 's have'} no {priceNoun} for that
              date, so {comparison.unpriced_intervals === 1 ? 'it is' : 'they are'} left out of the
              total.{' '}
              {otherIsElectric
                ? 'Add an electricity tariff covering those dates.'
                : 'Refresh the EU fuel prices from the Admin tab, or add prices manually.'}
            </p>
          </div>
        </GlassCard>
      )}

      <section aria-label="Cost comparison" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label={`${yourName} would cost`}
          value={`€${fmt(comparison.actual_cost)}`}
          hint={`${fmt(comparison.your_quantity, 1)} ${yourUnitLabel} at ${comparison.your_basis} ${comparison.basis_label}`}
        />
        <StatTile
          label={`${theirName} would cost`}
          value={`€${fmt(comparison.alternative_cost)}`}
          hint={`${fmt(comparison.quantity, 1)} ${comparison.unit_label} at ${comparison.basis} ${comparison.basis_label}`}
          accent="var(--series-2)"
        />
        <StatTile
          label={units.system === 'imperial' ? 'Yours per mile' : 'Yours per 100km'}
          value={units.costPerDistance(comparison.actual_cost_per_100km)}
          accent="var(--accent-3)"
        />
        <StatTile
          label={units.system === 'imperial' ? 'Theirs per mile' : 'Theirs per 100km'}
          value={units.costPerDistance(comparison.alternative_cost_per_100km)}
          accent="var(--series-2)"
        />
      </section>

      <p className="mt-2 text-xs text-ink-3">
        Both cars are costed from the consumption figure you entered for each, over the same{' '}
        {units.distance(comparison.distance_km)}
        {sameFuel
          ? ', at the price you actually paid per ' + comparison.unit_label + '.'
          : `, yours at what you paid and the ${theirName} at the going rate for ${otherFuel.toLowerCase()}.`}{' '}
        You actually spent <span className="text-ink-2">€{fmt(comparison.actual_spend)}</span> over
        that stretch — the difference from the figure above is your real driving against the
        quoted one.
      </p>

      <section aria-label="Emissions" className="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label={`${yourName} emits`}
          value={comparison.actual_co2_kg != null ? fmt(comparison.actual_co2_kg, 1) : '—'}
          unit="kg CO2"
          hint={
            comparison.actual_co2_g_per_km != null
              ? `${fmt(comparison.actual_co2_g_per_km, 0)} g/km`
              : undefined
          }
          accent="var(--accent-3)"
        />
        <StatTile
          label={`${theirName} emits`}
          value={fmt(comparison.alternative_co2_kg, 1)}
          unit="kg CO2"
          hint={
            comparison.alternative_co2_g_per_km != null
              ? `${fmt(comparison.alternative_co2_g_per_km, 0)} g/km`
              : undefined
          }
          accent="var(--series-2)"
        />
        <StatTile
          label={cleaner ? 'CO2 avoided' : 'CO2 added'}
          value={fmt(Math.abs(comparison.co2_saving_kg), 1)}
          unit="kg"
          hint={cleaner ? 'by driving yours' : 'over the alternative'}
          accent={cleaner ? 'var(--good)' : 'var(--critical)'}
        />
        {electricityInvolved && (
          <StatTile
            label="Grid intensity"
            value={fmt(comparison.grid_co2_g_per_kwh, 0)}
            unit="g/kWh"
            hint="What electricity is assumed to cost the atmosphere"
            accent="var(--accent-2)"
          />
        )}
      </section>

      <p className="mt-2 text-xs text-ink-3">
        Emissions count burning the fuel{electricityInvolved && ' and generating the electricity'}.
        They exclude refining, manufacturing and the battery, so this compares the two on the same
        terms rather than claiming to be a full lifecycle figure.
      </p>

      <GlassCard className="mt-4 p-6">
        <div className="flex items-start gap-3">
          {/* icon + label, so the status colour never carries the meaning alone */}
          <svg
            aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none"
            stroke={ahead ? 'var(--good)' : 'var(--critical)'}
            strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 shrink-0"
          >
            {ahead ? <path d="M12 19V5M5 12l7-7 7 7" /> : <path d="M12 5v14M19 12l-7 7-7-7" />}
          </svg>
          <div>
            <p className="text-sm font-medium text-ink">
              {ahead ? `${yourName} is the cheaper car` : `${theirName} would be cheaper`}
            </p>
            <p className="readout mt-1 text-3xl font-semibold text-ink">
              €{fmt(Math.abs(comparison.saving))}
            </p>
            <p className="mt-1 text-sm text-ink-2">
              {ahead ? 'saved' : 'extra'} over {units.distance(comparison.distance_km)}
              {comparison.alternative_cost > 0 &&
                ` · ${fmt(Math.abs(comparison.saving / comparison.alternative_cost) * 100, 0)}% ${ahead ? 'less' : 'more'}`}
            </p>
            <p className="mt-3 text-xs text-ink-3">
              {yourName} at {comparison.your_basis} {comparison.basis_label} against{' '}
              {comparison.comparison_vehicle} at {comparison.basis} {comparison.basis_label}. The
              first {eventNoun(mine.fuel_type)} is excluded — it paid for driving from before you
              started logging.
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
                  each stretch at the {priceNoun} that applied when it ended
                </span>
              </caption>
              <thead>
                <tr className="border-b border-edge text-left">
                  {[
                    'Period',
                    'Distance',
                    comparison.unit_label,
                    `Price/${comparison.unit_label}`,
                    'Priced as of',
                    `${theirName} cost`,
                  ].map(h => (
                    <th key={h} className="px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-ink-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparison.intervals.map(i => (
                  <tr key={`${i.start_date}-${i.end_date}`} className="border-b border-edge last:border-0">
                    <td className="readout px-4 py-3 text-ink-2">{i.start_date} → {i.end_date}</td>
                    <td className="readout px-4 py-3 text-ink">{units.distance(i.distance_km)}</td>
                    <td className="readout px-4 py-3 text-ink-2">{fmt(i.quantity, 1)}</td>
                    <td className="readout px-4 py-3 text-ink">
                      {i.unit_price != null ? `€${fmt(i.unit_price, 3)}` : '—'}
                    </td>
                    <td className="readout px-4 py-3 text-ink-3">{i.price_as_of ?? '—'}</td>
                    <td className="readout px-4 py-3 font-medium text-ink">
                      {i.cost != null ? `€${fmt(i.cost)}` : '—'}
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
