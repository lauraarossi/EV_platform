import { useState } from 'react'
import {
  getChargingSessions,
  createChargingSession,
  updateChargingSession,
  deleteChargingSession,
} from '../api/charging'
import { getVehicles } from '../api/vehicles'
import { getIntervals } from '../api/stats'
import type { ChargingSession, ChargingSessionInput, Interval } from '../types'
import { CHARGER_LABEL } from '../types'
import { useAsync } from '../hooks/useAsync'
import { useUnits } from '../hooks/useUnits'
import PageHeader from '../components/PageHeader'
import GlassCard from '../components/GlassCard'
import Modal from '../components/Modal'
import ChargeForm from '../components/ChargeForm'
import VehiclePicker from '../components/VehiclePicker'
import { Loading, ErrorState, EmptyState } from '../components/States'

export default function Charges() {
  const { units } = useUnits()
  const [vehicleId, setVehicleId] = useState<number | null>(null)
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState<ChargingSession | null>(null)

  const { data, error, loading, reload } = useAsync(async () => {
    const vehicles = await getVehicles()
    const owned = vehicles.filter(v => !v.is_comparison_vehicle)
    const selected = vehicleId ?? owned[0]?.id ?? null
    const sessions = selected ? await getChargingSessions(selected) : []
    const intervalData = selected ? await getIntervals(selected) : { intervals: [], anomalies: [] }
    return { vehicles, owned, selected, sessions, ...intervalData }
  }, [vehicleId])

  if (loading) return <Loading label="Loading charges…" />
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (!data) return null

  const { owned, selected, sessions, intervals, anomalies } = data

  if (owned.length === 0) {
    return (
      <>
        <PageHeader title="Charges" subtitle="Log a charge and the odometer reading." />
        <EmptyState title="Add a vehicle first" body="You need a car in the Garage before you can log charges against it." />
      </>
    )
  }

  // The interval ending at a given charge describes the driving that preceded it.
  const intervalTo = new Map<number, Interval>(intervals.map(i => [i.to_session_id, i]))
  const latestOdometer = sessions.length
    ? Math.max(...sessions.map(s => s.odometer_km))
    : null

  const save = async (payload: ChargingSessionInput) => {
    if (editing) await updateChargingSession(editing.id, payload)
    else await createChargingSession(payload)
    setEditing(null)
    setAdding(false)
    reload()
  }

  const remove = async (s: ChargingSession) => {
    if (!confirm(`Delete the charge logged on ${s.date}?`)) return
    await deleteChargingSession(s.id)
    reload()
  }

  return (
    <>
      <PageHeader
        title="Charges"
        subtitle={
          sessions.length
            ? `${sessions.length} logged · latest odometer ${units.distance(latestOdometer)}`
            : 'Log a charge and the odometer reading.'
        }
        action={
          <button onClick={() => setAdding(true)} className="btn-primary focus-ring rounded-lg px-4 py-2 text-sm font-medium">
            Log charge
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

      {sessions.length === 0 ? (
        <EmptyState
          title="No charges logged yet"
          body="Log your first charge with the odometer reading. Efficiency figures appear once there's a second one to measure against."
          action={
            <button onClick={() => setAdding(true)} className="btn-primary focus-ring rounded-lg px-4 py-2 text-sm font-medium">
              Log your first charge
            </button>
          }
        />
      ) : (
        <GlassCard>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[56rem] text-sm">
              <thead>
                <tr className="border-b border-edge text-left">
                  {['Date', `Odometer (${units.distanceUnit})`, 'Since last', 'Added', 'Battery', 'Cost', units.efficiencyUnit, 'Charger', ''].map(h => (
                    <th key={h} className="px-3 py-3 text-[11px] font-medium uppercase tracking-wider text-ink-3">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sessions.map(s => {
                  const iv = intervalTo.get(s.id)
                  return (
                    <tr key={s.id} className="border-b border-edge last:border-0">
                      <td className="readout px-3 py-3 text-ink-2">
                        {s.date}
                        {s.time_of_day && <span className="text-ink-3"> {s.time_of_day.slice(0, 5)}</span>}
                      </td>
                      <td className="readout px-3 py-3 font-medium text-ink">
                        {units.distanceValue(s.odometer_km)}
                      </td>
                      <td className="readout px-3 py-3 text-ink-2">
                        {iv ? units.distance(iv.distance_km) : '—'}
                      </td>
                      <td className="readout px-3 py-3 text-ink">{s.kwh_added} kWh</td>
                      <td className="readout px-3 py-3 text-ink-2">
                        {s.soc_start_pct != null && s.soc_end_pct != null
                          ? `${s.soc_start_pct}→${s.soc_end_pct}%`
                          : '—'}
                      </td>
                      <td className="readout px-3 py-3 text-ink">
                        {s.cost != null ? `€${s.cost.toFixed(2)}` : '—'}
                      </td>
                      <td className="readout px-3 py-3">
                        {iv?.efficiency_kwh_per_100km != null ? (
                          <span className="text-ink">
                            {units.efficiency(iv.efficiency_kwh_per_100km)}
                            {/* an approximated figure must say so, not look identical to a measured one */}
                            {!iv.energy_is_exact && (
                              <span title="Approximate — battery % wasn't recorded" className="text-ink-3"> ~</span>
                            )}
                          </span>
                        ) : (
                          <span className="text-ink-3">—</span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-ink-2">
                        {CHARGER_LABEL[s.charger_type]}
                        {s.location_city && <span className="text-ink-3"> · {s.location_city}</span>}
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex justify-end gap-1">
                          <button onClick={() => setEditing(s)} className="focus-ring rounded px-2 py-1 text-xs text-ink-3 hover:text-ink">
                            Edit
                          </button>
                          <button
                            onClick={() => remove(s)}
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
          {intervals.some(i => !i.energy_is_exact) && (
            <p className="border-t border-edge px-3 py-2.5 text-xs text-ink-3">
              ~ marks an approximate figure: without the battery % either side, we assume the energy
              added equals the energy used.
            </p>
          )}
        </GlassCard>
      )}

      <Modal
        open={adding || editing !== null}
        title={editing ? 'Edit charge' : 'Log charge'}
        onClose={() => { setAdding(false); setEditing(null) }}
      >
        <ChargeForm
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
