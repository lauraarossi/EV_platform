import { useState } from 'react'
import {
  getFuelEvents,
  createFuelEvent,
  updateFuelEvent,
  deleteFuelEvent,
} from '../api/fuelEvents'
import { getVehicles } from '../api/vehicles'
import { getIntervals } from '../api/stats'
import type { FuelEvent, FuelEventInput, Interval, Vehicle } from '../types'
import { CHARGER_LABEL } from '../types'
import { EventNoun, burnsFuel, eventNoun, takesElectricity } from '../fuel'
import { useAsync } from '../hooks/useAsync'
import { useUnits } from '../hooks/useUnits'
import PageHeader from '../components/PageHeader'
import GlassCard from '../components/GlassCard'
import Modal from '../components/Modal'
import FuelEventForm from '../components/FuelEventForm'
import VehiclePicker from '../components/VehiclePicker'
import { Loading, ErrorState, EmptyState } from '../components/States'

/** Whichever figure this car is measured by, with its unit. */
function consumptionCell(iv: Interval | undefined, vehicle: Vehicle, units: ReturnType<typeof useUnits>['units']) {
  if (!iv) return null
  if (takesElectricity(vehicle.fuel_type) && iv.efficiency_kwh_per_100km != null) {
    return { value: units.efficiency(iv.efficiency_kwh_per_100km), exact: iv.energy_is_exact }
  }
  if (burnsFuel(vehicle.fuel_type) && iv.consumption_l_per_100km != null) {
    return { value: units.consumption(iv.consumption_l_per_100km), exact: iv.volume_is_exact }
  }
  return null
}

export default function Charges() {
  const { units } = useUnits()
  const [vehicleId, setVehicleId] = useState<number | null>(null)
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState<FuelEvent | null>(null)

  const { data, error, loading, reload } = useAsync(async () => {
    const vehicles = await getVehicles()
    const owned = vehicles.filter(v => v.is_owned)
    const selected = vehicleId ?? owned[0]?.id ?? null
    const events = selected ? await getFuelEvents(selected) : []
    const intervalData = selected ? await getIntervals(selected) : { intervals: [], anomalies: [] }
    return { vehicles, owned, selected, events, ...intervalData }
  }, [vehicleId])

  if (loading) return <Loading label="Loading your log…" />
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (!data) return null

  const { owned, selected, events, intervals, anomalies } = data

  if (owned.length === 0) {
    return (
      <>
        <PageHeader title="Log" subtitle="Record a fill-up and the odometer reading." />
        <EmptyState
          title="Add a vehicle first"
          body="You need a car in the Garage before you can log anything against it."
        />
      </>
    )
  }

  const vehicle = owned.find(v => v.id === selected) ?? owned[0]
  const fuel = vehicle.fuel_type
  const electric = takesElectricity(fuel)
  const liquid = burnsFuel(fuel)
  const noun = eventNoun(fuel)

  // The interval ending at a given event describes the driving that preceded it.
  const intervalTo = new Map<number, Interval>(intervals.map(i => [i.to_event_id, i]))
  const latestOdometer = events.length ? Math.max(...events.map(e => e.odometer_km)) : null

  const save = async (payload: FuelEventInput) => {
    if (editing) await updateFuelEvent(editing.id, payload)
    else await createFuelEvent(payload)
    setEditing(null)
    setAdding(false)
    reload()
  }

  const remove = async (e: FuelEvent) => {
    if (!confirm(`Delete the ${noun} logged on ${e.date}?`)) return
    await deleteFuelEvent(e.id)
    reload()
  }

  const columns = [
    'Date',
    `Odometer (${units.distanceUnit})`,
    'Since last',
    'Added',
    electric && liquid ? 'Levels' : electric ? 'Battery' : 'Tank',
    'Cost',
    electric ? units.efficiencyUnit : units.consumptionUnit,
    electric ? 'Charger' : 'Where',
    '',
  ]

  const approximated = intervals.some(i =>
    electric ? i.energy_used_kwh != null && !i.energy_is_exact
             : i.volume_used_litres != null && !i.volume_is_exact,
  )

  return (
    <>
      <PageHeader
        title={EventNoun(fuel, true)}
        subtitle={
          events.length
            ? `${events.length} logged · latest odometer ${units.distance(latestOdometer)}`
            : `Record a ${noun} and the odometer reading.`
        }
        action={
          <button
            onClick={() => setAdding(true)}
            className="btn-primary focus-ring rounded-lg px-4 py-2 text-sm font-medium"
          >
            Log {noun}
          </button>
        }
      />

      {owned.length > 1 && (
        <div className="mb-4">
          <VehiclePicker vehicles={owned} value={selected!} onChange={setVehicleId} />
        </div>
      )}

      {anomalies.length > 0 && (
        <GlassCard className="mb-4 p-4">
          <div className="flex items-start gap-2.5">
            <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" strokeWidth="2" strokeLinecap="round" className="mt-0.5 shrink-0">
              <path d="M12 9v4M12 17v.01M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6A2 2 0 0 0 22 18L13.7 3.9a2 2 0 0 0-3.4 0z" />
            </svg>
            <div>
              <p className="text-sm font-medium text-ink">Check these entries</p>
              <ul className="mt-1 space-y-0.5 text-sm text-ink-2">
                {anomalies.map((a, i) => <li key={i}>{a}</li>)}
              </ul>
            </div>
          </div>
        </GlassCard>
      )}

      {events.length === 0 ? (
        <EmptyState
          title={`No ${eventNoun(fuel, true)} logged yet`}
          body={`Log your first ${noun} with the odometer reading. Consumption figures appear once there's a second one to measure against.`}
          action={
            <button
              onClick={() => setAdding(true)}
              className="btn-primary focus-ring rounded-lg px-4 py-2 text-sm font-medium"
            >
              Log your first {noun}
            </button>
          }
        />
      ) : (
        <GlassCard>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[56rem] text-sm">
              <thead>
                <tr className="border-b border-edge text-left">
                  {columns.map(h => (
                    <th key={h} className="px-3 py-3 text-[11px] font-medium uppercase tracking-wider text-ink-3">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {events.map(e => {
                  const iv = intervalTo.get(e.id)
                  const consumption = consumptionCell(iv, vehicle, units)
                  const added = [
                    e.energy_kwh != null ? `${e.energy_kwh} kWh` : null,
                    e.volume_litres != null ? `${e.volume_litres} L` : null,
                  ].filter(Boolean).join(' · ')
                  const levels = [
                    e.soc_start_pct != null && e.soc_end_pct != null
                      ? `${e.soc_start_pct}→${e.soc_end_pct}%`
                      : null,
                    e.tank_start_pct != null && e.tank_end_pct != null
                      ? `${e.tank_start_pct}→${e.tank_end_pct}%`
                      : null,
                  ].filter(Boolean).join(' · ')

                  return (
                    <tr key={e.id} className="border-b border-edge last:border-0">
                      <td className="readout px-3 py-3 text-ink-2">
                        {e.date}
                        {e.time_of_day && <span className="text-ink-3"> {e.time_of_day.slice(0, 5)}</span>}
                      </td>
                      <td className="readout px-3 py-3 font-medium text-ink">
                        {units.distanceValue(e.odometer_km)}
                      </td>
                      <td className="readout px-3 py-3 text-ink-2">
                        {iv ? units.distance(iv.distance_km) : '—'}
                      </td>
                      <td className="readout px-3 py-3 text-ink">{added || '—'}</td>
                      <td className="readout px-3 py-3 text-ink-2">{levels || '—'}</td>
                      <td className="readout px-3 py-3 text-ink">
                        {e.cost != null ? `€${e.cost.toFixed(2)}` : '—'}
                      </td>
                      <td className="readout px-3 py-3">
                        {consumption ? (
                          <span className="text-ink">
                            {consumption.value}
                            {/* an approximated figure must say so, not look identical to a measured one */}
                            {!consumption.exact && (
                              <span title="Approximate — the level either side wasn't recorded" className="text-ink-3"> ~</span>
                            )}
                          </span>
                        ) : (
                          <span className="text-ink-3">—</span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-ink-2">
                        {e.charger_type ? CHARGER_LABEL[e.charger_type] : ''}
                        {e.location_city && (
                          <span className="text-ink-3">
                            {e.charger_type ? ' · ' : ''}{e.location_city}
                          </span>
                        )}
                        {!e.charger_type && !e.location_city && '—'}
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex justify-end gap-1">
                          <button onClick={() => setEditing(e)} className="focus-ring rounded px-2 py-1 text-xs text-ink-3 hover:text-ink">
                            Edit
                          </button>
                          <button
                            onClick={() => remove(e)}
                            className="focus-ring rounded px-2 py-1 text-xs hover:underline"
                            style={{ color: 'var(--critical)' }}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {approximated && (
            <p className="border-t border-edge px-3 py-2.5 text-xs text-ink-3">
              ~ marks an approximate figure: without the {electric ? 'battery' : 'fuel'} % either
              side, we assume what went in equals what was used.
            </p>
          )}
        </GlassCard>
      )}

      <Modal
        open={adding || editing !== null}
        title={editing ? `Edit ${noun}` : `Log ${noun}`}
        onClose={() => { setAdding(false); setEditing(null) }}
      >
        <FuelEventForm
          vehicles={owned}
          existing={editing ?? undefined}
          defaultVehicleId={selected ?? undefined}
          lastOdometer={editing ? null : latestOdometer}
          onSubmit={save}
          onCancel={() => { setAdding(false); setEditing(null) }}
        />
      </Modal>
    </>
  )
}
