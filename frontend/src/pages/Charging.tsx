import { getChargingSessions } from '../api/charging'
import { getVehicles } from '../api/vehicles'
import type { ChargerType } from '../types'
import { useAsync } from '../hooks/useAsync'
import PageHeader from '../components/PageHeader'
import GlassCard from '../components/GlassCard'
import { Loading, ErrorState, EmptyState } from '../components/States'

const CHARGER_LABEL: Record<ChargerType, string> = {
  ac_home: 'Home AC',
  ac_public: 'Public AC',
  dc_rapid: 'DC rapid',
  dc_ultra: 'DC ultra',
}

export default function Charging() {
  const { data, error, loading, reload } = useAsync(
    () => Promise.all([getChargingSessions(), getVehicles()]),
    []
  )

  if (loading) return <Loading label="Loading charging sessions…" />
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (!data) return null

  const [sessions, vehicles] = data
  const nameOf = (id: number) => {
    const v = vehicles.find(x => x.id === id)
    return v ? `${v.make} ${v.model}` : `#${id}`
  }

  const totalKwh = sessions.reduce((s, c) => s + c.kwh_charged, 0)
  const totalCost = sessions.reduce((s, c) => s + (c.cost ?? 0), 0)

  return (
    <>
      <PageHeader
        title="Charging"
        subtitle={
          sessions.length
            ? `${sessions.length} session${sessions.length === 1 ? '' : 's'} · ${totalKwh.toFixed(1)} kWh · €${totalCost.toFixed(2)}`
            : 'Track what you actually pay to charge.'
        }
      />

      {sessions.length === 0 ? (
        <EmptyState title="No charging sessions yet" body="Log a charge to start tracking your real cost per kWh." />
      ) : (
        <GlassCard>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[48rem] text-sm">
              <thead>
                <tr className="border-b border-edge text-left">
                  {['Date', 'Vehicle', 'Charger', 'Location', 'Energy', 'Cost', '€/kWh'].map(h => (
                    <th key={h} className="px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-ink-3">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sessions.map(c => (
                  <tr key={c.id} className="border-b border-edge last:border-0">
                    <td className="readout px-4 py-3 text-ink-2">
                      {c.date}
                      {c.time_of_day && <span className="text-ink-3"> {c.time_of_day.slice(0, 5)}</span>}
                    </td>
                    <td className="px-4 py-3 text-ink">{nameOf(c.vehicle_id)}</td>
                    <td className="px-4 py-3">
                      <span className="text-ink-2">{CHARGER_LABEL[c.charger_type]}</span>
                      {c.charger_capacity_kw != null && (
                        <span className="readout text-ink-3"> · {c.charger_capacity_kw} kW</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-ink-2">{c.location_city ?? '—'}</td>
                    <td className="readout px-4 py-3 font-medium text-ink">{c.kwh_charged} kWh</td>
                    <td className="readout px-4 py-3 text-ink">{c.cost != null ? `€${c.cost.toFixed(2)}` : '—'}</td>
                    <td className="readout px-4 py-3 text-ink-2">
                      {c.cost != null && c.kwh_charged > 0 ? `€${(c.cost / c.kwh_charged).toFixed(3)}` : '—'}
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
