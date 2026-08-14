import { useState, type FormEvent } from 'react'
import type { CatalogVehicle, Vehicle, VehicleInput } from '../types'
import { TRANSMISSION_LABEL } from '../types'
import { Field, TextInput, Select, FormError } from './form'
import CatalogPicker from './CatalogPicker'

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

export default function VehicleForm({
  existing,
  onSubmit,
  onCancel,
}: {
  existing?: Vehicle
  onSubmit: (data: VehicleInput) => Promise<void>
  onCancel: () => void
}) {
  const [f, setF] = useState({
    make: existing?.make ?? '',
    model: existing?.model ?? '',
    trim: existing?.trim ?? '',
    year: existing ? String(existing.year) : String(new Date().getFullYear()),
    nickname: existing?.nickname ?? '',
    image_url: existing?.image_url ?? '',
    fuel_type: existing?.fuel_type ?? '',
    transmission: existing?.transmission ?? '',
    is_comparison_vehicle: existing?.is_comparison_vehicle ?? false,
    battery_capacity_kwh: existing?.battery_capacity_kwh != null ? String(existing.battery_capacity_kwh) : '',
    onboard_charger_kw: existing?.onboard_charger_kw != null ? String(existing.onboard_charger_kw) : '',
    wltp_range_km: existing?.wltp_range_km != null ? String(existing.wltp_range_km) : '',
    engine_size_cc: existing?.engine_size_cc != null ? String(existing.engine_size_cc) : '',
    fuel_consumption_l_per_100km: existing?.fuel_consumption_l_per_100km != null ? String(existing.fuel_consumption_l_per_100km) : '',
    horsepower: existing?.horsepower != null ? String(existing.horsepower) : '',
    zero_to_100_seconds: existing?.zero_to_100_seconds != null ? String(existing.zero_to_100_seconds) : '',
    top_speed_kmh: existing?.top_speed_kmh != null ? String(existing.top_speed_kmh) : '',
    kerb_weight_kg: existing?.kerb_weight_kg != null ? String(existing.kerb_weight_kg) : '',
  })
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const set = (k: keyof typeof f) => (e: { target: { value: string } }) =>
    setF(prev => ({ ...prev, [k]: e.target.value }))

  const isEv = f.fuel_type === 'electric'

  /** Fill the form from a catalogue entry. Every field stays editable, and
   *  anything the catalogue lacks (charging specs, for instance) is left as
   *  typed rather than being blanked. */
  const applyCatalogEntry = (c: CatalogVehicle) => {
    const str = (v: number | null | undefined) => (v == null ? '' : String(v))
    setF(prev => ({
      ...prev,
      make: c.make,
      // The catalogue's variant name carries the trim, e.g. "…Techno 52".
      model: c.model,
      trim: c.variant.replace(`${c.make} ${c.model}`, '').trim() || prev.trim,
      year: c.model_year ? String(c.model_year) : prev.year,
      fuel_type: c.fuel_type,
      transmission: c.transmission ?? prev.transmission,
      image_url: c.image_url ?? prev.image_url,
      battery_capacity_kwh: str(c.battery_capacity_kwh) || prev.battery_capacity_kwh,
      onboard_charger_kw: str(c.onboard_charger_kw) || prev.onboard_charger_kw,
      wltp_range_km: str(c.wltp_range_km) || prev.wltp_range_km,
      engine_size_cc: str(c.engine_size_cc) || prev.engine_size_cc,
      fuel_consumption_l_per_100km:
        str(c.fuel_consumption_l_per_100km) || prev.fuel_consumption_l_per_100km,
      horsepower: str(c.horsepower) || prev.horsepower,
      zero_to_100_seconds: str(c.zero_to_100_seconds) || prev.zero_to_100_seconds,
      top_speed_kmh: str(c.top_speed_kmh) || prev.top_speed_kmh,
      kerb_weight_kg: str(c.kerb_weight_kg) || prev.kerb_weight_kg,
    }))
  }

  async function handle(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await onSubmit({
        make: f.make,
        model: f.model,
        trim: f.trim || null,
        year: Number(f.year),
        fuel_type: f.fuel_type as VehicleInput['fuel_type'],
        transmission: (f.transmission || null) as VehicleInput['transmission'],
        nickname: f.nickname || null,
        image_url: f.image_url || null,
        battery_capacity_kwh: isEv ? num(f.battery_capacity_kwh) : null,
        onboard_charger_kw: isEv ? num(f.onboard_charger_kw) : null,
        wltp_range_km: isEv ? num(f.wltp_range_km) : null,
        engine_size_cc: isEv ? null : num(f.engine_size_cc),
        fuel_consumption_l_per_100km: isEv ? null : num(f.fuel_consumption_l_per_100km),
        horsepower: num(f.horsepower),
        zero_to_100_seconds: num(f.zero_to_100_seconds),
        top_speed_kmh: num(f.top_speed_kmh),
        kerb_weight_kg: num(f.kerb_weight_kg),
        is_comparison_vehicle: f.is_comparison_vehicle,
      })
    } catch (err) {
      setError(describeError(err))
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handle} className="space-y-5">
      <FormError message={error} />

      {/* Offered only when adding: when editing, the fields already hold your
          own corrections and a prefill would quietly overwrite them.
          Reg lookup is hidden for now — a plate only proves year and county.
          RegLookupField and /catalog/lookup/registration remain in place for
          when a provider can give make and model. */}
      {!existing && (
        <CatalogPicker onPick={applyCatalogEntry} onClear={() => {}} />
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Make" required>
          <TextInput value={f.make} onChange={set('make')} required placeholder="Renault" />
        </Field>
        <Field label="Model" required>
          <TextInput value={f.model} onChange={set('model')} required placeholder="R4 E-Tech" />
        </Field>
        <Field label="Trim">
          <TextInput value={f.trim} onChange={set('trim')} placeholder="Techno" />
        </Field>
        <Field label="Year" required>
          <TextInput type="number" min="1900" max="2100" value={f.year} onChange={set('year')} required />
        </Field>
      </div>

      {/* No photo field: image_url is still carried on the model and gets set
          when the catalogue supplies one, it just isn't hand-entered. */}
      <Field label="Nickname" hint="Shown instead of make/model where space is tight">
        <TextInput value={f.nickname} onChange={set('nickname')} placeholder="The wee blue one" />
      </Field>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Fuel type" required>
          <Select value={f.fuel_type} onChange={set('fuel_type')} required>
            <option value="">Select…</option>
            <option value="electric">Electric</option>
            <option value="petrol">Petrol</option>
            <option value="diesel">Diesel</option>
            <option value="hybrid">Hybrid</option>
          </Select>
        </Field>
        {/* Free text with suggestions: no catalogue records a transmission,
            and real gearboxes don't fit a fixed list ("7-speed DSG"). */}
        <Field label="Transmission" hint="Pick one or type your own">
          <TextInput
            list="transmission-options"
            value={f.transmission}
            onChange={set('transmission')}
            placeholder="e.g. Automatic"
          />
          <datalist id="transmission-options">
            {Object.values(TRANSMISSION_LABEL).map(label => (
              <option key={label} value={label} />
            ))}
          </datalist>
        </Field>
        <div className="flex items-end">
          <label className="flex cursor-pointer items-center gap-2.5 pb-2">
            <input
              type="checkbox"
              checked={f.is_comparison_vehicle}
              onChange={e => setF(p => ({ ...p, is_comparison_vehicle: e.target.checked }))}
              className="focus-ring h-4 w-4 rounded border-edge"
            />
            <span className="text-sm text-ink">
              Comparison car
              <span className="block text-[11px] text-ink-3">
                A car you're measuring against, not one you drive
              </span>
            </span>
          </label>
        </div>
      </div>

      {f.fuel_type === '' ? null : isEv ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Battery (kWh)" hint="Needed for exact efficiency">
            <TextInput type="number" step="0.1" min="0" value={f.battery_capacity_kwh} onChange={set('battery_capacity_kwh')} placeholder="52" />
          </Field>
          <Field label="Onboard charger (kW)">
            <TextInput type="number" step="0.1" min="0" value={f.onboard_charger_kw} onChange={set('onboard_charger_kw')} placeholder="11" />
          </Field>
          <Field label="WLTP range (km)">
            <TextInput type="number" step="1" min="0" value={f.wltp_range_km} onChange={set('wltp_range_km')} placeholder="409" />
          </Field>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Engine (cc)">
            <TextInput type="number" step="1" min="0" value={f.engine_size_cc} onChange={set('engine_size_cc')} placeholder="1333" />
          </Field>
          <Field label="Consumption (L/100km)" hint="Required for the petrol comparison">
            <TextInput type="number" step="0.1" min="0" value={f.fuel_consumption_l_per_100km} onChange={set('fuel_consumption_l_per_100km')} placeholder="6.0" />
          </Field>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Power (hp)">
          <TextInput type="number" step="1" min="0" value={f.horsepower} onChange={set('horsepower')} placeholder="148" />
        </Field>
        <Field label="0–100 (s)">
          <TextInput type="number" step="0.1" min="0" value={f.zero_to_100_seconds} onChange={set('zero_to_100_seconds')} placeholder="8.2" />
        </Field>
        <Field label="Top speed (km/h)">
          <TextInput type="number" step="1" min="0" value={f.top_speed_kmh} onChange={set('top_speed_kmh')} placeholder="150" />
        </Field>
        <Field label="Kerb weight (kg)">
          <TextInput type="number" step="1" min="0" value={f.kerb_weight_kg} onChange={set('kerb_weight_kg')} placeholder="1462" />
        </Field>
      </div>

      <div className="flex justify-end gap-2 border-t border-edge pt-4">
        <button type="button" onClick={onCancel} className="focus-ring rounded-lg border border-edge px-4 py-2 text-sm font-medium text-ink-2 hover:text-ink">
          Cancel
        </button>
        <button type="submit" disabled={saving} className="btn-primary focus-ring rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-60">
          {saving ? 'Saving…' : existing ? 'Save changes' : 'Add vehicle'}
        </button>
      </div>
    </form>
  )
}
