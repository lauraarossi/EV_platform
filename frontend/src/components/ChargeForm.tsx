import { useState, type FormEvent } from 'react'
import type { ChargingSession, ChargingSessionInput, Vehicle } from '../types'
import { CHARGER_LABEL, DRIVING_MIX_LABEL } from '../types'
import { Field, TextInput, Select, FormError } from './form'
import { useUnits } from '../hooks/useUnits'

const today = () => new Date().toISOString().slice(0, 10)

/** Pull a useful message out of a FastAPI 422 body rather than showing [object Object]. */
function describeError(e: unknown): string {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map(d => {
        const loc = Array.isArray(d.loc) ? d.loc.filter((p: unknown) => p !== 'body').join('.') : ''
        return loc ? `${loc}: ${d.msg}` : d.msg
      })
      .join(' · ')
  }
  return e instanceof Error ? e.message : 'Could not save'
}

const num = (v: string): number | null => (v.trim() === '' ? null : Number(v))

export default function ChargeForm({
  vehicles,
  existing,
  defaultVehicleId,
  lastOdometer,
  onSubmit,
  onCancel,
}: {
  vehicles: Vehicle[]
  existing?: ChargingSession
  defaultVehicleId?: number
  lastOdometer?: number | null
  onSubmit: (data: ChargingSessionInput) => Promise<void>
  onCancel: () => void
}) {
  const { units } = useUnits()
  const [f, setF] = useState({
    vehicle_id: String(existing?.vehicle_id ?? defaultVehicleId ?? vehicles[0]?.id ?? ''),
    date: existing?.date ?? today(),
    time_of_day: existing?.time_of_day?.slice(0, 5) ?? '',
    // Held in the *displayed* unit while editing; converted back on submit.
    odometer_km: existing ? String(Number(units.fromKm(existing.odometer_km).toFixed(1))) : '',
    kwh_added: existing ? String(existing.kwh_added) : '',
    cost: existing?.cost != null ? String(existing.cost) : '',
    soc_start_pct: existing?.soc_start_pct != null ? String(existing.soc_start_pct) : '',
    soc_end_pct: existing?.soc_end_pct != null ? String(existing.soc_end_pct) : '',
    charger_type: existing?.charger_type ?? 'ac_home',
    charger_capacity_kw: existing?.charger_capacity_kw != null ? String(existing.charger_capacity_kw) : '',
    location_city: existing?.location_city ?? '',
    driving_mix: existing?.driving_mix ?? '',
    notes: existing?.notes ?? '',
  })
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const set = (k: keyof typeof f) => (e: { target: { value: string } }) =>
    setF(prev => ({ ...prev, [k]: e.target.value }))

  // Mirrors the server rule so the user finds out before submitting.
  const socStart = num(f.soc_start_pct)
  const socEnd = num(f.soc_end_pct)
  const socHalfFilled = (socStart === null) !== (socEnd === null)
  const socInverted = socStart !== null && socEnd !== null && socEnd <= socStart
  const odoTooLow =
    lastOdometer != null &&
    f.odometer_km.trim() !== '' &&
    units.toKm(Number(f.odometer_km)) < lastOdometer

  async function handle(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (socHalfFilled) return setError('Enter both start and end % — or neither.')
    if (socInverted) return setError('End % must be higher than start %.')

    setSaving(true)
    try {
      await onSubmit({
        vehicle_id: Number(f.vehicle_id),
        date: f.date,
        time_of_day: f.time_of_day ? `${f.time_of_day}:00` : null,
        odometer_km: units.toKm(Number(f.odometer_km)),
        kwh_added: Number(f.kwh_added),
        cost: num(f.cost),
        currency: 'EUR',
        soc_start_pct: socStart,
        soc_end_pct: socEnd,
        charger_type: f.charger_type as ChargingSessionInput['charger_type'],
        charger_capacity_kw: num(f.charger_capacity_kw),
        location_city: f.location_city || null,
        country: 'IE',
        driving_mix: (f.driving_mix || null) as ChargingSessionInput['driving_mix'],
        notes: f.notes || null,
      })
    } catch (err) {
      setError(describeError(err))
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handle} className="space-y-5">
      <FormError message={error} />

      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Vehicle" required>
          <Select value={f.vehicle_id} onChange={set('vehicle_id')} required>
            {vehicles.map(v => (
              <option key={v.id} value={v.id}>
                {v.nickname || `${v.make} ${v.model}`}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Date" required>
          <TextInput type="date" value={f.date} onChange={set('date')} required />
        </Field>
        <Field label="Time">
          <TextInput type="time" value={f.time_of_day} onChange={set('time_of_day')} />
        </Field>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field
          label={`Odometer (${units.distanceUnit})`}
          required
          hint={lastOdometer != null ? `Last logged: ${units.distance(lastOdometer)}` : undefined}
        >
          <TextInput
            type="number" step="0.1" min="0" required
            value={f.odometer_km} onChange={set('odometer_km')}
            placeholder={units.system === 'imperial' ? 'e.g. 7755' : 'e.g. 12480'}
          />
        </Field>
        <Field label="Energy added (kWh)" required>
          <TextInput
            type="number" step="0.01" min="0.01" required
            value={f.kwh_added} onChange={set('kwh_added')}
            placeholder="e.g. 31.2"
          />
        </Field>
        <Field label="Cost (€)">
          <TextInput type="number" step="0.01" min="0" value={f.cost} onChange={set('cost')} placeholder="e.g. 7.80" />
        </Field>
      </div>

      {odoTooLow && (
        <p className="text-xs" style={{ color: 'var(--warning)' }}>
          ⚠ That’s lower than your last reading ({lastOdometer!.toLocaleString()} km). Saving it will
          flag an anomaly in your stats.
        </p>
      )}

      <div className="rounded-xl border border-edge p-4">
        <p className="text-[11px] uppercase tracking-wider text-ink-3">Battery %</p>
        <p className="mt-1 text-xs text-ink-3">
          Optional, but it makes efficiency exact — without it we assume the energy you added equals
          what you used, which is wrong whenever you change your charge target.
        </p>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <Field label="% when plugged in">
            <TextInput type="number" step="1" min="0" max="100" value={f.soc_start_pct} onChange={set('soc_start_pct')} placeholder="e.g. 20" />
          </Field>
          <Field label="% when unplugged">
            <TextInput type="number" step="1" min="0" max="100" value={f.soc_end_pct} onChange={set('soc_end_pct')} placeholder="e.g. 80" />
          </Field>
        </div>
        {socHalfFilled && (
          <p className="mt-2 text-xs" style={{ color: 'var(--warning)' }}>
            Enter both or neither — one alone can’t describe the charge.
          </p>
        )}
        {socInverted && (
          <p className="mt-2 text-xs" style={{ color: 'var(--warning)' }}>
            End % must be higher than start %.
          </p>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Charger" required>
          <Select value={f.charger_type} onChange={set('charger_type')}>
            {Object.entries(CHARGER_LABEL).map(([v, label]) => (
              <option key={v} value={v}>{label}</option>
            ))}
          </Select>
        </Field>
        <Field label="Charger kW">
          <TextInput type="number" step="0.1" min="0" value={f.charger_capacity_kw} onChange={set('charger_capacity_kw')} placeholder="e.g. 7.4" />
        </Field>
        <Field label="City">
          <TextInput value={f.location_city} onChange={set('location_city')} placeholder="e.g. Dublin" />
        </Field>
        <Field label="Driving" hint="Since the last charge">
          <Select value={f.driving_mix} onChange={set('driving_mix')}>
            <option value="">—</option>
            {Object.entries(DRIVING_MIX_LABEL).map(([v, label]) => (
              <option key={v} value={v}>{label}</option>
            ))}
          </Select>
        </Field>
      </div>

      <Field label="Notes">
        <TextInput value={f.notes} onChange={set('notes')} placeholder="Anything worth remembering" />
      </Field>

      <div className="flex justify-end gap-2 border-t border-edge pt-4">
        <button type="button" onClick={onCancel} className="focus-ring rounded-lg border border-edge px-4 py-2 text-sm font-medium text-ink-2 hover:text-ink">
          Cancel
        </button>
        <button type="submit" disabled={saving} className="btn-primary focus-ring rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-60">
          {saving ? 'Saving…' : existing ? 'Save changes' : 'Log charge'}
        </button>
      </div>
    </form>
  )
}
