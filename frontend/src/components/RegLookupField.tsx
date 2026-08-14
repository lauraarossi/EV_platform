import { useState } from 'react'
import { lookupRegistration, type RegLookup } from '../api/catalog'
import { Field, TextInput } from './form'

/**
 * Decode an Irish registration.
 *
 * The plate itself proves the year and county, so those come back instantly
 * with no lookup. Make and model do not: they live in the National Vehicle and
 * Driver File, which isn't publicly accessible — commercial resellers licence
 * it and charge per lookup. So this fills in what it honestly can and points
 * you at the picker for the rest.
 */
export default function RegLookupField({
  onDecoded,
}: {
  onDecoded: (r: RegLookup) => void
}) {
  const [reg, setReg] = useState('')
  const [result, setResult] = useState<RegLookup | null>(null)
  const [busy, setBusy] = useState(false)

  const run = async () => {
    if (reg.trim().length < 4) return
    setBusy(true)
    try {
      const r = await lookupRegistration(reg.trim())
      setResult(r)
      if (r.year) onDecoded(r)
    } catch {
      setResult({
        registration: reg,
        valid: false,
        year: null,
        half: null,
        county: null,
        county_code: null,
        make: null,
        model: null,
        notes: ['Lookup failed — enter the details by hand.'],
      })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-xl border border-edge p-4">
      <p className="text-[11px] uppercase tracking-wider text-ink-3">Have the reg?</p>
      <p className="mt-1 text-xs text-ink-3">
        Fills in the year and county. Make and model aren’t in any public database, so pick those
        below.
      </p>

      <div className="mt-3 flex items-end gap-2">
        <div className="flex-1">
          <Field label="Registration">
            <TextInput
              value={reg}
              onChange={e => setReg(e.target.value.toUpperCase())}
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  run()
                }
              }}
              placeholder="251-D-12345"
              autoComplete="off"
            />
          </Field>
        </div>
        <button
          type="button"
          onClick={run}
          disabled={busy || reg.trim().length < 4}
          className="focus-ring mb-[1px] rounded-lg border border-edge px-3 py-2 text-sm font-medium text-ink-2 hover:text-ink disabled:opacity-50"
        >
          {busy ? 'Reading…' : 'Read'}
        </button>
      </div>

      {result && (
        <div className="mt-2 text-xs">
          {result.year ? (
            <p className="text-ink-2">
              <span className="text-ink">
                {result.year}
                {result.half ? (result.half === 1 ? ' (Jan–Jun)' : ' (Jul–Dec)') : ''}
              </span>
              {result.county && <span> · {result.county}</span>}
            </p>
          ) : (
            <p style={{ color: 'var(--warning)' }}>{result.notes[0]}</p>
          )}
        </div>
      )}
    </div>
  )
}
