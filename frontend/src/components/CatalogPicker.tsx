import { useEffect, useState } from 'react'
import { getMakes, getModels, getVariants } from '../api/catalog'
import type { CatalogMake, CatalogModel, CatalogVehicle, FuelType } from '../types'
import { Field, Select } from './form'

/**
 * A variant's label, with enough added to tell it from its namesakes.
 *
 * Two Audi e-tron GT "quattro" entries are different cars — 105 kWh and
 * 93.4 kWh — but the catalogue's variant name says only "quattro", so the
 * dropdown showed the same thing twice. Rather than pad every label, the
 * distinguishing spec is added only where a name is actually shared.
 */
function labelFor(v: CatalogVehicle, all: CatalogVehicle[]): string {
  const shared = all.filter(o => o.variant === v.variant).length > 1
  if (!shared) return v.variant

  const marks = [
    v.battery_capacity_kwh ? `${v.battery_capacity_kwh} kWh` : null,
    v.wltp_range_km ? `${Math.round(v.wltp_range_km)} km` : null,
    v.horsepower ? `${v.horsepower} hp` : null,
  ].filter(Boolean)

  return marks.length ? `${v.variant} · ${marks.join(' · ')}` : v.variant
}

/**
 * Cascading make -> model -> variant picker.
 *
 * The dropdowns are keyed by the API's `make_key`/`model_key` rather than the
 * displayed name: three catalogues spell one car three ways ("ZOE", "Zoe",
 * "New ZOE"), and the keys are what fold those into a single entry.
 *
 * Choosing a variant hands the whole spec back — the parent form prefills from
 * it, and every field stays editable afterwards.
 */
export default function CatalogPicker({
  onPick,
  onClear,
}: {
  onPick: (entry: CatalogVehicle) => void
  onClear: () => void
}) {
  // Its own filter rather than the form's fuel type: that defaulted to
  // Electric, so petrol and diesel cars looked missing until you knew to
  // change it first. Empty means every fuel.
  const [fuelType, setFuelType] = useState<FuelType | ''>('')
  const [makes, setMakes] = useState<CatalogMake[]>([])
  const [models, setModels] = useState<CatalogModel[]>([])
  const [variants, setVariants] = useState<CatalogVehicle[]>([])

  const [makeKey, setMakeKey] = useState('')
  const [modelKey, setModelKey] = useState('')
  const [variantId, setVariantId] = useState('')

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setMakeKey('')
    getMakes(fuelType || undefined)
      .then(setMakes)
      .catch(() => setError('Catalogue unavailable'))
      .finally(() => setLoading(false))
  }, [fuelType])

  useEffect(() => {
    setModels([])
    setVariants([])
    setModelKey('')
    setVariantId('')
    if (!makeKey) return
    getModels(makeKey, fuelType || undefined)
      .then(setModels)
      .catch(() => setError('Could not load models'))
  }, [makeKey, fuelType])

  useEffect(() => {
    setVariants([])
    setVariantId('')
    if (!makeKey || !modelKey) return
    getVariants(makeKey, modelKey)
      .then(setVariants)
      .catch(() => setError('Could not load variants'))
  }, [makeKey, modelKey])

  const chooseVariant = (id: string) => {
    setVariantId(id)
    const entry = variants.find(v => v.id === id)
    if (entry) onPick(entry)
  }

  const reset = () => {
    setMakeKey('')
    setModelKey('')
    setVariantId('')
    onClear()
  }

  const picked = variants.find(v => v.id === variantId)

  if (error) {
    return (
      <div className="rounded-xl border border-edge p-4">
        <p className="text-sm text-ink-2">{error} — fill the fields in by hand below.</p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-edge p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-wider text-ink-3">
            Find your car
          </p>
          <p className="mt-1 text-xs text-ink-3">
            Fills the specs in for you, from EU registration data and an open EV database.
          </p>
        </div>
        {(makeKey || modelKey || variantId) && (
          <button
            type="button"
            onClick={reset}
            className="focus-ring shrink-0 rounded-lg px-2 py-1 text-xs text-ink-3 hover:text-ink"
          >
            Clear
          </button>
        )}
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Fuel">
          <Select
            value={fuelType}
            onChange={e => setFuelType(e.target.value as FuelType | '')}
          >
            <option value="">All</option>
            <option value="electric">Electric</option>
            <option value="petrol">Petrol</option>
            <option value="diesel">Diesel</option>
            <option value="hybrid">Hybrid</option>
          </Select>
        </Field>

        <Field label="Make">
          <Select value={makeKey} onChange={e => setMakeKey(e.target.value)} disabled={loading}>
            <option value="">{loading ? 'Loading…' : 'Select…'}</option>
            {makes.map(m => (
              <option key={m.make_key} value={m.make_key}>
                {m.make}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Model">
          <Select value={modelKey} onChange={e => setModelKey(e.target.value)} disabled={!makeKey}>
            <option value="">{makeKey ? 'Select…' : '—'}</option>
            {models.map(m => (
              <option key={m.model_key} value={m.model_key}>
                {m.model}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Version">
          <Select
            value={variantId}
            onChange={e => chooseVariant(e.target.value)}
            disabled={!modelKey}
          >
            <option value="">{modelKey ? 'Select…' : '—'}</option>
            {variants.map(v => (
              <option key={v.id} value={v.id}>
                {labelFor(v, variants)}
                {v.model_year ? ` (${v.model_year})` : ''}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      {picked && (
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-3">
          <span className="text-ink-2">Filled in from {picked.source_name}</span>
          {picked.licence && <span>· {picked.licence}</span>}
          {picked.data_quality && <span>· {picked.data_quality}</span>}
          {picked.consumption_real_world_kwh_100km != null && (
            <span>
              · real-world estimate {picked.consumption_real_world_kwh_100km} kWh/100km
            </span>
          )}
        </div>
      )}
    </div>
  )
}
