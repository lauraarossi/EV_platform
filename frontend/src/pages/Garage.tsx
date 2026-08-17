import { useState } from 'react'
import { getVehicles, createVehicle, updateVehicle, deleteVehicle } from '../api/vehicles'
import { getSummary } from '../api/stats'
import type { Summary, Vehicle, VehicleInput } from '../types'
import { TRANSMISSION_LABEL } from '../types'
import { useAsync } from '../hooks/useAsync'
import { useUnits } from '../hooks/useUnits'
import PageHeader from '../components/PageHeader'
import GlassCard from '../components/GlassCard'
import Modal from '../components/Modal'
import VehicleForm from '../components/VehicleForm'
import { Loading, ErrorState, EmptyState } from '../components/States'

function Spec({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wider text-ink-3">{label}</dt>
      <dd className="readout mt-0.5 text-sm font-medium text-ink">{value}</dd>
    </div>
  )
}

function StatusStrip({ s }: { s: Summary }) {
  const { units } = useUnits()
  const items: [string, string][] = [
    ['Odometer', units.distance(s.latest_odometer_km)],
    ['Charges', String(s.session_count)],
    ['Efficiency', s.avg_efficiency_kwh_per_100km != null
      ? `${units.efficiency(s.avg_efficiency_kwh_per_100km)} ${units.efficiencyUnit}` : '—'],
    ['Tracked', s.total_distance_km > 0 ? units.distance(s.total_distance_km) : '—'],
  ]
  return (
    <div className="mt-4 grid grid-cols-2 gap-3 rounded-xl border border-edge p-3 sm:grid-cols-4">
      {items.map(([label, value]) => (
        <div key={label}>
          <p className="text-[10px] uppercase tracking-wider text-ink-3">{label}</p>
          <p className="readout mt-0.5 text-sm font-semibold text-ink">{value}</p>
        </div>
      ))}
    </div>
  )
}

function VehicleCard({
  v,
  summary,
  onEdit,
  onDelete,
}: {
  v: Vehicle
  summary?: Summary
  onEdit: () => void
  onDelete: () => void
}) {
  const { units } = useUnits()
  const isEv = v.fuel_type === 'electric'

  return (
    <GlassCard interactive className="overflow-hidden">
      {v.image_url && (
        <img
          src={v.image_url}
          alt=""
          className="h-40 w-full object-cover"
          onError={e => ((e.target as HTMLImageElement).style.display = 'none')}
        />
      )}

      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-ink">
              {v.nickname || `${v.make} ${v.model}`}
            </h2>
            <p className="mt-0.5 text-sm text-ink-3">
              {v.nickname ? `${v.make} ${v.model} · ` : ''}
              {v.year}
              {v.trim ? ` · ${v.trim}` : ''}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <span
              className="rounded-full px-2.5 py-1 text-[11px] font-medium capitalize"
              style={{
                color: isEv ? 'var(--accent-2)' : 'var(--ink-2)',
                background: isEv
                  ? 'color-mix(in oklab, var(--accent-2) 14%, transparent)'
                  : 'color-mix(in oklab, var(--ink) 8%, transparent)',
                border: `1px solid ${isEv ? 'color-mix(in oklab, var(--accent-2) 30%, transparent)' : 'var(--border)'}`,
              }}
            >
              {v.is_comparison_vehicle ? 'comparison' : v.fuel_type}
            </span>
          </div>
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
          {isEv ? (
            <>
              {v.battery_capacity_kwh != null && <Spec label="Battery" value={`${v.battery_capacity_kwh} kWh`} />}
              {v.onboard_charger_kw != null && <Spec label="AC charger" value={`${v.onboard_charger_kw} kW`} />}
              {v.wltp_range_km != null && <Spec label="WLTP" value={units.distance(v.wltp_range_km)} />}
            </>
          ) : (
            <>
              {v.engine_size_cc != null && <Spec label="Engine" value={`${v.engine_size_cc} cc`} />}
              {v.fuel_consumption_l_per_100km != null && (
                <Spec
                  label="Consumption"
                  value={`${units.consumption(v.fuel_consumption_l_per_100km)} ${units.consumptionUnit}`}
                />
              )}
            </>
          )}
          {v.horsepower != null && <Spec label="Power" value={`${v.horsepower} hp`} />}
          {v.transmission && (
            <Spec label="Transmission" value={TRANSMISSION_LABEL[v.transmission]} />
          )}
          {v.zero_to_100_seconds != null && <Spec label="0–100" value={`${v.zero_to_100_seconds} s`} />}
          {v.top_speed_kmh != null && (
            <Spec label="Top speed" value={`${units.distanceValue(v.top_speed_kmh)} ${units.distanceUnit}/h`} />
          )}
          {v.kerb_weight_kg != null && <Spec label="Weight" value={units.weight(v.kerb_weight_kg)} />}
        </dl>

        {!v.is_comparison_vehicle && summary && <StatusStrip s={summary} />}

        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onEdit} className="focus-ring rounded-lg border border-edge px-3 py-1.5 text-xs font-medium text-ink-2 hover:text-ink">
            Edit
          </button>
          <button
            onClick={onDelete}
            className="focus-ring rounded-lg border px-3 py-1.5 text-xs font-medium"
            style={{ borderColor: 'color-mix(in oklab, var(--critical) 35%, transparent)', color: 'var(--critical)' }}
          >
            Delete
          </button>
        </div>
      </div>
    </GlassCard>
  )
}

export default function Garage() {
  const [editing, setEditing] = useState<Vehicle | null>(null)
  const [adding, setAdding] = useState(false)

  const { data, error, loading, reload } = useAsync(async () => {
    const vehicles = await getVehicles()
    // Status strip is only meaningful for cars you actually drive.
    const owned = vehicles.filter(v => !v.is_comparison_vehicle)
    const summaries = await Promise.all(owned.map(v => getSummary(v.id).catch(() => null)))
    const byId = new Map<number, Summary>()
    owned.forEach((v, i) => summaries[i] && byId.set(v.id, summaries[i]!))
    return { vehicles, summaries: byId }
  }, [])

  if (loading) return <Loading label="Loading your garage…" />
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (!data) return null

  const { vehicles, summaries } = data
  const owned = vehicles.filter(v => !v.is_comparison_vehicle)
  const comparisons = vehicles.filter(v => v.is_comparison_vehicle)

  const save = async (payload: VehicleInput) => {
    if (editing) await updateVehicle(editing.id, payload)
    else await createVehicle(payload)
    setEditing(null)
    setAdding(false)
    reload()
  }

  const remove = async (v: Vehicle) => {
    const n = summaries.get(v.id)?.session_count ?? 0
    const warning = n > 0 ? `\n\nThis will also delete ${n} charge record${n === 1 ? '' : 's'}.` : ''
    if (!confirm(`Delete ${v.nickname || `${v.make} ${v.model}`}?${warning}`)) return
    await deleteVehicle(v.id)
    reload()
  }

  return (
    <>
      <PageHeader
        title="Garage"
        subtitle="Your vehicles and their current status."
        action={
          <button onClick={() => setAdding(true)} className="btn-primary focus-ring rounded-lg px-4 py-2 text-sm font-medium">
            Add vehicle
          </button>
        }
      />

      {vehicles.length === 0 ? (
        <EmptyState
          title="Your garage is empty"
          body="Add your EV to start tracking what it really costs to run."
          action={
            <button onClick={() => setAdding(true)} className="btn-primary focus-ring rounded-lg px-4 py-2 text-sm font-medium">
              Add your EV
            </button>
          }
        />
      ) : (
        <div className="space-y-8">
          {owned.length > 0 && (
            <section>
              <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-ink-3">
                Yours ({owned.length})
              </h2>
              <div className="grid gap-3 lg:grid-cols-2">
                {owned.map(v => (
                  <VehicleCard
                    key={v.id} v={v} summary={summaries.get(v.id)}
                    onEdit={() => setEditing(v)} onDelete={() => remove(v)}
                  />
                ))}
              </div>
            </section>
          )}

          {comparisons.length > 0 && (
            <section>
              <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-ink-3">
                Comparison cars ({comparisons.length})
              </h2>
              <div className="grid gap-3 lg:grid-cols-2">
                {comparisons.map(v => (
                  <VehicleCard key={v.id} v={v} onEdit={() => setEditing(v)} onDelete={() => remove(v)} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}

      <Modal
        open={adding || editing !== null}
        title={editing ? 'Edit vehicle' : 'Add vehicle'}
        onClose={() => { setAdding(false); setEditing(null) }}
      >
        <VehicleForm
          existing={editing ?? undefined}
          onSubmit={save}
          onCancel={() => { setAdding(false); setEditing(null) }}
        />
      </Modal>
    </>
  )
}
