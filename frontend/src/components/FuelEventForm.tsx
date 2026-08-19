import { useState, type FormEvent } from 'react'
import type { FuelEvent, FuelEventInput, Vehicle } from '../types'
import { CHARGER_LABEL, DRIVING_MIX_LABEL } from '../types'
import { burnsFuel, takesElectricity } from '../fuel'
import { useCurrency } from '../hooks/useCurrency'
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

/**
 * Logging one refuelling, for whatever the car takes.
 *
 * The form follows the selected vehicle: an EV shows kWh, battery % and the
 * charger; a petrol car shows litres and tank %; a plug-in hybrid shows both,
 * since one stop can add each.
 */
export default function FuelEventForm({
  vehicles,
  existing,
  defaultVehicleId,
  lastOdometer,
  onSubmit,
  onCancel,
}: {
  vehicles: Vehicle[]
  existing?: FuelEvent
  defaultVehicleId?: number
  lastOdometer?: number | null
  onSubmit: (data: FuelEventInput) => Promise<void>
  onCancel: () => void
}) {
  const { units } = useUnits()
  const money = useCurrency()
  const [f, setF] = useState({
    vehicle_id: String(existing?.vehicle_id ?? defaultVehicleId ?? vehicles[0]?.id ?? ''),
    date: existing?.date ?? today(),
    time_of_day: existing?.time_of_day?.slice(0, 5) ?? '',
    // Held in the *displayed* unit while editing; converted back on submit.
    odometer_km: existing ? String(Number(units.fromKm(existing.odometer_km).toFixed(1))) : '',
    energy_kwh: existing?.energy_kwh != null ? String(existing.energy_kwh) : '',
    volume_litres: existing?.volume_litres != null ? String(existing.volume_litres) : '',
    cost: existing?.cost != null ? String(existing.cost) : '',
    soc_start_pct: existing?.soc_start_pct != null ? String(existing.soc_start_pct) : '',
    soc_end_pct: existing?.soc_end_pct != null ? String(existing.soc_end_pct) : '',
    tank_start_pct: existing?.tank_start_pct != null ? String(existing.tank_start_pct) : '',
    tank_end_pct: existing?.tank_end_pct != null ? String(existing.tank_end_pct) : '',
    charger_type: existing?.charger_type ?? 'ac_home',
    charger_capacity_kw:
      existing?.charger_capacity_kw != null ? String(existing.charger_capacity_kw) : '',
    location_city: existing?.location_city ?? '',
    driving_mix: existing?.driving_mix ?? '',
    notes: existing?.notes ?? '',
  })
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const set = (k: keyof typeof f) => (e: { target: { value: string } }) =>
    setF(prev => ({ ...prev, [k]: e.target.value }))

  const vehicle = vehicles.find(v => String(v.id) === f.vehicle_id) ?? vehicles[0]
  const fuel = vehicle?.fuel_type ?? 'electric'
  const electric = takesElectricity(fuel)
  const liquid = burnsFuel(fuel)

  // Mirrors the server rules so the user finds out before submitting.
  const pair = (a: string, b: string) => {
    const start = num(a)
    const end = num(b)
    return {
      start,
      end,
      halfFilled: (start === null) !== (end === null),
      inverted: start !== null && end !== null && end <= start,
    }
  }
  const soc = pair(f.soc_start_pct, f.soc_end_pct)
  const tank = pair(f.tank_start_pct, f.tank_end_pct)

  const nothingAdded =
    (!electric || f.energy_kwh.trim() === '') && (!liquid || f.volume_litres.trim() === '')

  const odoTooLow =
    lastOdometer != null &&
    f.odometer_km.trim() !== '' &&
    units.toKm(Number(f.odometer_km)) < lastOdometer

  async function handle(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (nothingAdded) return setError('Record what went in — energy, fuel, or both.')
    if (soc.halfFilled || tank.halfFilled)
      return setError('Enter both start and end % — or neither.')
    if (soc.inverted || tank.inverted) return setError('End % must be higher than start %.')

    setSaving(true)
    try {
      await onSubmit({
        vehicle_id: Number(f.vehicle_id),
        date: f.date,
        time_of_day: f.time_of_day ? `${f.time_of_day}:00` : null,
        odometer_km: units.toKm(Number(f.odometer_km)),
        energy_kwh: electric ? num(f.energy_kwh) : null,
        volume_litres: liquid ? num(f.volume_litres) : null,
        cost: num(f.cost),
        currency: 'EUR',
        soc_start_pct: electric ? soc.start : null,
        soc_end_pct: electric ? soc.end : null,
        tank_start_pct: liquid ? tank.start : null,
        tank_end_pct: liquid ? tank.end : null,
        charger_type: electric ? (f.charger_type as FuelEventInput['charger_type']) : null,
        charger_capacity_kw: electric ? num(f.charger_capacity_kw) : null,
        location_city: f.location_city || null,
        country: 'IE',
        driving_mix: (f.driving_mix || null) as FuelEventInput['driving_mix'],
        notes: f.notes || null,
      })
    } catch (err) {
      setError(describeError(err))
      setSaving(false)
    }
  }

  /** The level pair either side, which is what makes consumption exact. */
  const levelBlock = (
    kind: 'soc' | 'tank',
    title: string,
    explanation: string,
    startLabel: string,
    endLabel: string,
    state: ReturnType<typeof pair>,
  ) => (
    <div className="rounded-xl border border-edge p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[11px] uppercase tracking-wider text-ink-3">{title}</p>
        {kind === 'tank' && (
          <button
            type="button"
            onClick={() => setF(p => ({ ...p, tank_end_pct: '100' }))}
            className="focus-ring rounded-lg px-2 py-0.5 text-xs text-ink-3 hover:text-ink"
          >
            Filled to full
          </button>
        )}
      </div>
      <p className="mt-1 text-xs text-ink-3">{explanation}</p>
      <div className="mt-3 grid gap-4 sm:grid-cols-2">
        <Field label={startLabel}>
          <TextInput
            type="number" step="1" min="0" max="100"
            value={f[`${kind}_start_pct` as keyof typeof f]}
            onChange={set(`${kind}_start_pct` as keyof typeof f)}
            placeholder="e.g. 20"
          />
        </Field>
        <Field label={endLabel}>
          <TextInput
            type="number" step="1" min="0" max="100"
            value={f[`${kind}_end_pct` as keyof typeof f]}
            onChange={set(`${kind}_end_pct` as keyof typeof f)}
            placeholder="e.g. 80"
          />
        </Field>
      </div>
      {state.halfFilled && (
        <p className="mt-2 text-xs" style={{ color: 'var(--warning)' }}>
          Enter both or neither — one alone can’t describe it.
        </p>
      )}
      {state.inverted && (
        <p className="mt-2 text-xs" style={{ color: 'var(--warning)' }}>
          End % must be higher than start %.
        </p>
      )}
    </div>
  )

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

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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

        {electric && (
          <Field label="Energy added (kWh)" required={!liquid}>
            <TextInput
              type="number" step="0.01" min="0.01" required={!liquid}
              value={f.energy_kwh} onChange={set('energy_kwh')}
              placeholder="e.g. 31.2"
            />
          </Field>
        )}
        {liquid && (
          <Field label="Fuel added (L)" required={!electric}>
            <TextInput
              type="number" step="0.01" min="0.01" required={!electric}
              value={f.volume_litres} onChange={set('volume_litres')}
              placeholder="e.g. 37.5"
            />
          </Field>
        )}

        <Field label={`Cost (${money.symbol.trim()})`}>
          <TextInput
            type="number" step="0.01" min="0"
            value={f.cost} onChange={set('cost')} placeholder="e.g. 7.80"
          />
        </Field>
      </div>

      {odoTooLow && (
        <p className="text-xs" style={{ color: 'var(--warning)' }}>
          ⚠ That’s lower than your last reading ({units.distance(lastOdometer!)}). Saving it will
          flag an anomaly in your stats.
        </p>
      )}

      {electric &&
        levelBlock(
          'soc',
          'Battery %',
          'Optional, but it makes efficiency exact — without it we assume the energy you added equals what you used, which is wrong whenever you change your charge target.',
          '% when plugged in',
          '% when unplugged',
          soc,
        )}

      {liquid &&
        levelBlock(
          'tank',
          'Fuel level %',
          'Optional, but it makes consumption exact — without it we assume the fuel you added equals what you burned, which is wrong whenever you put in €30 rather than filling the tank.',
          '% before filling',
          '% after filling',
          tank,
        )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {electric && (
          <>
            <Field label="Charger">
              <Select value={f.charger_type ?? 'ac_home'} onChange={set('charger_type')}>
                {Object.entries(CHARGER_LABEL).map(([v, label]) => (
                  <option key={v} value={v}>{label}</option>
                ))}
              </Select>
            </Field>
            <Field label="Charger kW">
              <TextInput
                type="number" step="0.1" min="0"
                value={f.charger_capacity_kw} onChange={set('charger_capacity_kw')}
                placeholder="e.g. 7.4"
              />
            </Field>
          </>
        )}
        <Field label="City">
          <TextInput
            value={f.location_city} onChange={set('location_city')} placeholder="e.g. Dublin"
          />
        </Field>
        <Field label="Driving" hint="Since the last one">
          <Select value={f.driving_mix ?? ''} onChange={set('driving_mix')}>
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
        <button
          type="button" onClick={onCancel}
          className="focus-ring rounded-lg border border-edge px-4 py-2 text-sm font-medium text-ink-2 hover:text-ink"
        >
          Cancel
        </button>
        <button
          type="submit" disabled={saving}
          className="btn-primary focus-ring rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-60"
        >
          {saving ? 'Saving…' : existing ? 'Save changes' : 'Save'}
        </button>
      </div>
    </form>
  )
}
