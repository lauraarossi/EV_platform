/**
 * Wording that follows the car.
 *
 * The log holds a charge, a tank of petrol, or both, so the interface has to
 * say "charge" to an EV owner and "fill-up" to a petrol one. Kept in one place
 * rather than spelled out per page, so the vocabulary stays consistent.
 */
import type { FuelType } from './types'

export const takesElectricity = (fuel: FuelType) => fuel === 'electric' || fuel === 'hybrid'
export const burnsFuel = (fuel: FuelType) => fuel !== 'electric'

/** What one refuelling is called. A hybrid does both, so it gets the general word. */
export const eventNoun = (fuel: FuelType, plural = false) =>
  fuel === 'electric' ? (plural ? 'charges' : 'charge') : plural ? 'fill-ups' : 'fill-up'

/** Title case, for headings and buttons. */
export const EventNoun = (fuel: FuelType, plural = false) => {
  const word = eventNoun(fuel, plural)
  return word[0].toUpperCase() + word.slice(1)
}

/** How this car's running cost is quoted. */
export const consumptionUnit = (fuel: FuelType) =>
  fuel === 'electric' ? 'kWh/100km' : 'L/100km'

export const FUEL_LABEL: Record<FuelType, string> = {
  electric: 'Electric',
  petrol: 'Petrol',
  diesel: 'Diesel',
  hybrid: 'Hybrid',
}
