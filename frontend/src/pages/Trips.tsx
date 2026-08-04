import { getTrips } from '../api/trips'
import { getVehicles } from '../api/vehicles'
import { useAsync } from '../hooks/useAsync'
import PageHeader from '../components/PageHeader'
import GlassCard from '../components/GlassCard'
import { Loading, ErrorState, EmptyState } from '../components/States'

export default function Trips() {
  const { data, error, loading, reload } = useAsync(
    () => Promise.all([getTrips(), getVehicles()]),
    []
  )

  if (loading) return <Loading label="Loading trips…" />
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (!data) return null

  const [trips, vehicles] = data
  const nameOf = (id: number) => {
    const v = vehicles.find(x => x.id === id)
    return v ? `${v.make} ${v.model}` : `#${id}`
  }

  const totalKm = trips.reduce((s, t) => s + t.distance_km, 0)

  return (
    <>
      <PageHeader
        title="Trips"
        subtitle={trips.length ? `${trips.length} logged · ${totalKm.toFixed(0)} km total` : 'Log your journeys.'}
      />

      {trips.length === 0 ? (
        <EmptyState title="No trips yet" body="Log a journey to start building your real-world range picture." />
      ) : (
        <GlassCard>
          {/* Wide content scrolls inside its own container so the page never does */}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[42rem] text-sm">
              <thead>
                <tr className="border-b border-edge text-left">
                  {['Date', 'Vehicle', 'Route', 'Distance', 'Avg speed'].map(h => (
                    <th key={h} className="px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-ink-3">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {trips.map(t => (
                  <tr key={t.id} className="border-b border-edge last:border-0">
                    <td className="readout px-4 py-3 text-ink-2">{t.date}</td>
                    <td className="px-4 py-3 text-ink">{nameOf(t.vehicle_id)}</td>
                    <td className="px-4 py-3 text-ink-2">
                      {t.origin_city && t.destination_city
                        ? `${t.origin_city} → ${t.destination_city}`
                        : t.origin_city || t.destination_city || '—'}
                    </td>
                    <td className="readout px-4 py-3 font-medium text-ink">{t.distance_km} km</td>
                    <td className="readout px-4 py-3 text-ink-2">
                      {t.average_speed_kmh != null ? `${t.average_speed_kmh} km/h` : '—'}
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
