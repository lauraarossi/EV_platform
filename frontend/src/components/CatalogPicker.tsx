import { useEffect, useState } from 'react'
import { getMakes, getModels, getVariants } from '../api/catalog'
import type { CatalogMake, CatalogModel, CatalogVehicle, FuelType } from '../types'
import { Field, Select } from './form'

/**
 * Cascading make -> model -> variant picker.
 *
 * The catalogue's `trim_level` column is empty for every row, so the trim is
 * carried inside the variant name ("Techno 52"). That's why the third step is
 * "variant" rather than a separate trim dropdown.
 *
 * Choosing a variant hands the whole spec back — the parent form prefills from
 * it, and every field stays editable afterwards.
 */
export default function CatalogPicker({
  fuelType,
  onPick,
  onClear,
}: {
  /** Narrows the list to match the fuel type chosen on the form. */
  fuelType?: FuelType
  onPick: (entry: CatalogVehicle) => void
  onClear: () => void
}) {
  const [makes, setMakes] = useState<CatalogMake[]>([])
  const [models, setModels] = useState<CatalogModel[]>([])
  const [variants, setVariants] = useState<CatalogVehicle[]>([])

  const [make, setMake] = useState('')
  const [model, setModel] = useState('')
  const [variantId, setVariantId] = useState('')

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setMake('')
    getMakes(fuelType)
      .then(setMakes)
      .catch(() => setError('Catalogue unavailable'))
      .finally(() => setLoading(false))
  }, [fuelType])

  useEffect(() => {
    setModels([])
    setVariants([])
    setModel('')
    setVariantId('')
    if (!make) return
    getModels(make, fuelType).then(setModels).catch(() => setError('Could not load models'))
  }, [make])

  useEffect(() => {
    setVariants([])
    setVariantId('')
    if (!make || !model) return
    getVariants(make, model).then(setVariants).catch(() => setError('Could not load variants'))
  }, [make, model])

  const chooseVariant = (id: string) => {
    setVariantId(id)
    const entry = variants.find(v => v.id === id)
    if (entry) onPick(entry)
  }

  const reset = () => {
    setMake('')
    setModel('')
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
        {(make || model || variantId) && (
          <button
            type="button"
            onClick={reset}
            className="focus-ring shrink-0 rounded-lg px-2 py-1 text-xs text-ink-3 hover:text-ink"
          >
            Clear
          </button>
        )}
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <Field label="Make">
          <Select value={make} onChange={e => setMake(e.target.value)} disabled={loading}>
            <option value="">{loading ? 'Loading…' : 'Select…'}</option>
            {makes.map(m => (
              <option key={m.make} value={m.make}>
                {m.make} ({m.model_count})
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Model">
          <Select value={model} onChange={e => setModel(e.target.value)} disabled={!make}>
            <option value="">{make ? 'Select…' : '—'}</option>
            {models.map(m => (
              <option key={m.model} value={m.model}>
                {m.model} ({m.variant_count})
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Version">
          <Select value={variantId} onChange={e => chooseVariant(e.target.value)} disabled={!model}>
            <option value="">{model ? 'Select…' : '—'}</option>
            {variants.map(v => (
              <option key={v.id} value={v.id}>
                {v.variant}
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
