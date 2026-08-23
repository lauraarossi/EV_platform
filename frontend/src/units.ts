/**
 * Unit conversion for display and input.
 *
 * Everything is stored metric — the database, the API, the maths. This module
 * only converts at the edges: metric in, chosen units out for display, and
 * back to metric when reading a form. Storing whatever the user last picked
 * would make historical records ambiguous.
 */

export type UnitSystem = 'metric' | 'imperial'

const KM_PER_MILE = 1.609344
const KG_PER_LB = 0.45359237
// Ireland and the UK quote mpg in imperial gallons, not US.
const LITRES_PER_IMPERIAL_GALLON = 4.54609

export const kmToMiles = (km: number) => km / KM_PER_MILE
export const milesToKm = (miles: number) => miles * KM_PER_MILE
export const kgToLb = (kg: number) => kg / KG_PER_LB

/** kWh/100km is the metric convention; mi/kWh is how the imperial world talks. */
export const kwhPer100kmToMilesPerKwh = (v: number) =>
  v > 0 ? kmToMiles(100) / v : 0

/** L/100km to miles per imperial gallon. */
export const lPer100kmToMpg = (v: number) =>
  v > 0 ? kmToMiles(100) / (v / LITRES_PER_IMPERIAL_GALLON) : 0

const num = (v: number, digits: number) =>
  v.toLocaleString('en-IE', { minimumFractionDigits: digits, maximumFractionDigits: digits })

export interface Units {
  system: UnitSystem
  /** Short label for distance, for column headers and the like. */
  distanceUnit: string
  efficiencyUnit: string
  consumptionUnit: string
  /** The same figure the other way round, shown alongside.
   *
   *  Energy per distance and distance per energy are both in use, they point
   *  in opposite directions — less is better, then more is better — and which
   *  one a person reads fluently depends entirely on where they learned to
   *  drive. Cheaper to print both than to make anyone convert in their head. */
  efficiencyAltUnit: string
  consumptionAltUnit: string
  weightUnit: string

  distance: (km: number | null | undefined, digits?: number) => string
  /** Distance without the unit suffix, for tight table cells. */
  distanceValue: (km: number | null | undefined, digits?: number) => string
  efficiency: (kwhPer100km: number | null | undefined) => string
  consumption: (lPer100km: number | null | undefined) => string
  efficiencyAlt: (kwhPer100km: number | null | undefined) => string
  consumptionAlt: (lPer100km: number | null | undefined) => string
  weight: (kg: number | null | undefined) => string
  costPerDistance: (
    costPer100km: number | null | undefined,
    money?: (v: number, digits: number) => string,
  ) => string
  /** The cost per displayed distance unit, still in the base currency — the
   *  currency layer puts the symbol on. Separated from its suffix so a tile can
   *  set the suffix in small type rather than overflowing at heading size. */
  costPerDistanceAmount: (costPer100km: number | null | undefined) => number | null
  costUnit: string
  /** Emissions per unit of distance. Everything else on the page switches with
   *  the unit system, and this was left reading g/km in both. */
  co2Unit: string
  co2PerDistance: (gramsPerKm: number | null | undefined) => number | null
  /** Both sides quote per hundred, so both need the same two decimals. */
  costDigits: number

  /** Form helpers: what the user typed -> km for storage, and back. */
  toKm: (entered: number) => number
  fromKm: (km: number) => number
}

export function makeUnits(system: UnitSystem): Units {
  const imperial = system === 'imperial'

  const distanceValue = (km: number | null | undefined, digits = 0) => {
    if (km == null) return '—'
    return num(imperial ? kmToMiles(km) : km, digits)
  }

  return {
    system,
    distanceUnit: imperial ? 'mi' : 'km',
    // Per hundred leads on both sides, so the headline figure means the same
    // thing whichever system is chosen, and the familiar inverted form sits
    // beside it rather than replacing it.
    efficiencyUnit: imperial ? 'kWh/100mi' : 'kWh/100km',
    efficiencyAltUnit: imperial ? 'mi/kWh' : 'km/kWh',
    consumptionUnit: imperial ? 'mpg' : 'L/100km',
    consumptionAltUnit: imperial ? 'L/100km' : 'mpg',
    weightUnit: imperial ? 'lb' : 'kg',

    distanceValue,
    distance: (km, digits = 0) =>
      km == null ? '—' : `${distanceValue(km, digits)} ${imperial ? 'mi' : 'km'}`,

    efficiency: v => {
      if (v == null) return '—'
      // Energy per hundred of whichever distance unit is on display.
      return num(imperial ? v * KM_PER_MILE : v, 2)
    },

    efficiencyAlt: v => {
      if (v == null) return '—'
      // The inversion: more distance per kWh is better, less kWh per hundred
      // is better. Same measurement, opposite direction.
      const perKwh = imperial ? kwhPer100kmToMilesPerKwh(v) : 100 / v
      return num(perKwh, 2)
    },

    consumption: v => {
      if (v == null) return '—'
      return imperial ? num(lPer100kmToMpg(v), 1) : num(v, 1)
    },

    consumptionAlt: v => {
      if (v == null) return '—'
      return imperial ? num(v, 1) : num(lPer100kmToMpg(v), 1)
    },

    weight: kg => (kg == null ? '—' : `${num(imperial ? kgToLb(kg) : kg, 0)} ${imperial ? 'lb' : 'kg'}`),

    costUnit: imperial ? '/100mi' : '/100km',
    co2Unit: imperial ? 'g/mi' : 'g/km',
    co2PerDistance: gramsPerKm =>
      gramsPerKm == null ? null : imperial ? gramsPerKm * KM_PER_MILE : gramsPerKm,
    costDigits: 2,

    // Per hundred on both sides. Per single mile made the figure a fraction of
    // a currency unit — EUR 0.043 rather than EUR 4.32 — which is technically
    // right and useless to read, and not comparable with the metric one at a
    // glance either.
    costPerDistanceAmount: costPer100km => {
      if (costPer100km == null) return null
      return imperial ? costPer100km * KM_PER_MILE : costPer100km
    },

    costPerDistance: (costPer100km, money) => {
      if (costPer100km == null) return '—'
      const value = imperial ? costPer100km * KM_PER_MILE : costPer100km
      const shown = money ? money(value, 2) : `€${num(value, 2)}`
      return `${shown}${imperial ? '/100mi' : '/100km'}`
    },

    toKm: entered => (imperial ? milesToKm(entered) : entered),
    fromKm: km => (imperial ? kmToMiles(km) : km),
  }
}
