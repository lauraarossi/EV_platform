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
  weightUnit: string

  distance: (km: number | null | undefined, digits?: number) => string
  /** Distance without the unit suffix, for tight table cells. */
  distanceValue: (km: number | null | undefined, digits?: number) => string
  efficiency: (kwhPer100km: number | null | undefined) => string
  consumption: (lPer100km: number | null | undefined) => string
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
  /** Per mile needs a third decimal; per 100 km does not. */
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
    efficiencyUnit: imperial ? 'mi/kWh' : 'kWh/100km',
    consumptionUnit: imperial ? 'mpg' : 'L/100km',
    weightUnit: imperial ? 'lb' : 'kg',

    distanceValue,
    distance: (km, digits = 0) =>
      km == null ? '—' : `${distanceValue(km, digits)} ${imperial ? 'mi' : 'km'}`,

    efficiency: v => {
      if (v == null) return '—'
      // Note the inversion: more mi/kWh is better, less kWh/100km is better.
      return imperial ? num(kwhPer100kmToMilesPerKwh(v), 2) : num(v, 2)
    },

    consumption: v => {
      if (v == null) return '—'
      return imperial ? num(lPer100kmToMpg(v), 1) : num(v, 1)
    },

    weight: kg => (kg == null ? '—' : `${num(imperial ? kgToLb(kg) : kg, 0)} ${imperial ? 'lb' : 'kg'}`),

    costUnit: imperial ? '/mi' : '/100km',
    costDigits: imperial ? 3 : 2,

    costPerDistanceAmount: costPer100km => {
      if (costPer100km == null) return null
      return imperial ? costPer100km / kmToMiles(100) : costPer100km
    },

    costPerDistance: (costPer100km, money) => {
      if (costPer100km == null) return '—'
      // Per 100 km reads oddly in imperial; per mile is the familiar figure.
      const value = imperial ? costPer100km / kmToMiles(100) : costPer100km
      const digits = imperial ? 3 : 2
      const shown = money ? money(value, digits) : `€${num(value, digits)}`
      return `${shown}${imperial ? '/mi' : '/100km'}`
    },

    toKm: entered => (imperial ? milesToKm(entered) : entered),
    fromKm: km => (imperial ? kmToMiles(km) : km),
  }
}
