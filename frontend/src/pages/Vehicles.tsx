import { getVehicles } from '../api/vehicles'
import type { Vehicle } from '../types'
import { useAsync } from '../hooks/useAsync'
import PageHeader from '../components/PageHeader'
import GlassCard from '../components/GlassCard'
import { Loading, ErrorState, EmptyState } from '../components/States'

function Spec({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wider text-ink-3">{label}</dt>
      <dd className="readout mt-0.5 text-sm font-medium text-ink">{value}</dd>
    </div>
  )
}

function VehicleCard({ v }: { v: Vehicle }) {
  const isEv = v.fuel_type === 'electric'

  return (
    <GlassCard interactive className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">
            {v.make} {v.model}
          </h2>
          <p className="mt-0.5 text-sm text-ink-3">
            {v.year}
            {v.trim ? ` · ${v.trim}` : ''}
          </p>
        </div>

        <span
          className="rounded-full px-2.5 py-1 text-[11px] font-medium capitalize"
          style={{
            color: isEv ? 'var(--accent)' : 'var(--ink-2)',
            background: isEv
              ? 'color-mix(in oklab, var(--accent) 14%, transparent)'
              : 'color-mix(in oklab, var(--ink) 8%, transparent)',
            border: `1px solid ${isEv ? 'color-mix(in oklab, var(--accent) 30%, transparent)' : 'var(--border)'}`,
          }}
        >
          {v.is_comparison_vehicle ? 'comparison' : v.fuel_type}
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
        {isEv ? (
          <>
            {v.battery_capacity_kwh != null && <Spec label="Battery" value={`${v.battery_capacity_kwh} kWh`} />}
            {v.onboard_charger_kw != null && <Spec label="AC charger" value={`${v.onboard_charger_kw} kW`} />}
            {v.wltp_range_km != null && <Spec label="WLTP range" value={`${v.wltp_range_km} km`} />}
          </>
        ) : (
          <>
            {v.engine_size_cc != null && <Spec label="Engine" value={`${v.engine_size_cc} cc`} />}
            {v.fuel_consumption_l_per_100km != null && (
              <Spec label="Consumption" value={`${v.fuel_consumption_l_per_100km} L/100km`} />
            )}
          </>
        )}
        {v.horsepower != null && <Spec label="Power" value={`${v.horsepower} hp`} />}
        {v.zero_to_100_seconds != null && <Spec label="0–100" value={`${v.zero_to_100_seconds} s`} />}
        {v.kerb_weight_kg != null && <Spec label="Weight" value={`${v.kerb_weight_kg} kg`} />}
      </dl>
    </GlassCard>
  )
}

export default function Vehicles() {
  const { data: vehicles, error, loading, reload } = useAsync(getVehicles, [])

  if (loading) return <Loading label="Loading vehicles…" />
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (!vehicles) return null

  const evs = vehicles.filter(v => !v.is_comparison_vehicle)
  const comparisons = vehicles.filter(v => v.is_comparison_vehicle)

  return (
    <>
      <PageHeader
        title="Vehicles"
        subtitle="Your EVs, and the petrol cars you're measuring them against."
      />

      {vehicles.length === 0 ? (
        <EmptyState title="No vehicles yet" body="Add your EV to start tracking real-world costs." />
      ) : (
        <div className="space-y-8">
          <section>
            <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-ink-3">
              Electric ({evs.length})
            </h2>
            <div className="grid gap-3 lg:grid-cols-2">
              {evs.map(v => (
                <VehicleCard key={v.id} v={v} />
              ))}
            </div>
          </section>

          {comparisons.length > 0 && (
            <section>
              <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-ink-3">
                Petrol comparison ({comparisons.length})
              </h2>
              <div className="grid gap-3 lg:grid-cols-2">
                {comparisons.map(v => (
                  <VehicleCard key={v.id} v={v} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </>
  )
}
