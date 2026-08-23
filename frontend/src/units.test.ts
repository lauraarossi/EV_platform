/**
 * Unit conversion.
 *
 * The round-trip test is the important one: a value typed in miles, stored as
 * km, and shown again must come back unchanged, or editing a charge would
 * quietly drift the odometer every time it was saved.
 */
import { describe, expect, it } from 'vitest'
import { makeUnits, kmToMiles, milesToKm, lPer100kmToMpg, kwhPer100kmToMilesPerKwh } from './units'

describe('conversions', () => {
  it('converts km and miles', () => {
    expect(kmToMiles(100)).toBeCloseTo(62.137, 3)
    expect(milesToKm(62.137)).toBeCloseTo(100, 2)
  })

  it('round-trips without drift', () => {
    const units = makeUnits('imperial')
    const original = 12480
    expect(units.toKm(units.fromKm(original))).toBeCloseTo(original, 6)
  })

  it('uses imperial gallons for mpg, as Ireland and the UK do', () => {
    // 5 L/100km is about 56.5 mpg imperial, but only 47 mpg US.
    expect(lPer100kmToMpg(5)).toBeCloseTo(56.5, 1)
  })

  it('inverts efficiency: more mi/kWh is better, less kWh/100km is better', () => {
    const good = kwhPer100kmToMilesPerKwh(10)
    const bad = kwhPer100kmToMilesPerKwh(20)
    expect(good).toBeGreaterThan(bad)
    expect(good).toBeCloseTo(6.21, 2)
  })
})

describe('formatting', () => {
  it('labels metric', () => {
    const u = makeUnits('metric')
    expect(u.distance(1000)).toBe('1,000 km')
    expect(u.efficiencyUnit).toBe('kWh/100km')
    expect(u.consumptionUnit).toBe('L/100km')
  })

  it('labels imperial', () => {
    const u = makeUnits('imperial')
    expect(u.distance(1000)).toBe('621 mi')
    expect(u.efficiencyUnit).toBe('kWh/100mi')
    expect(u.efficiencyAltUnit).toBe('mi/kWh')
    expect(u.weight(1000)).toBe('2,205 lb')
  })

  it('quotes cost per hundred on both sides', () => {
    const u = makeUnits('imperial')
    // Per hundred on both sides: EUR 0.067/mi was right and unreadable.
    expect(u.costPerDistance(4.17)).toBe('€6.71/100mi')
    expect(makeUnits('metric').costPerDistance(4.17)).toBe('€4.17/100km')
  })

  it('shows a dash rather than zero for missing values', () => {
    const u = makeUnits('metric')
    expect(u.distance(null)).toBe('—')
    expect(u.efficiency(undefined)).toBe('—')
    expect(u.weight(null)).toBe('—')
  })
})

describe('cost per distance in a stat tile', () => {
  it('separates the amount from its suffix, so long values fit', () => {
    const metric = makeUnits('metric')
    expect(metric.costPerDistanceAmount(43.92)).toBeCloseTo(43.92, 2)
    expect(metric.costUnit).toBe('/100km')
    expect(metric.costDigits).toBe(2)

    // A mile is further than a kilometre, so a hundred of them cost more.
    const imperial = makeUnits('imperial')
    expect(imperial.costPerDistanceAmount(4.17)).toBeCloseTo(6.71, 2)
    expect(imperial.costUnit).toBe('/100mi')
    expect(imperial.costDigits).toBe(2)
  })

  it('leaves the currency symbol to the layer that knows it', () => {
    // Amounts are held in euro and converted for display, so units.ts must not
    // stamp a euro sign on a figure that may be shown in pounds.
    expect(makeUnits('metric').costPerDistanceAmount(null)).toBeNull()
    expect(makeUnits('metric').costPerDistance(43.92, v => `£${v.toFixed(2)}`))
      .toBe('£43.92/100km')
  })
})

describe('emissions per distance', () => {
  it('is per kilometre in metric', () => {
    const u = makeUnits('metric')
    expect(u.co2Unit).toBe('g/km')
    expect(u.co2PerDistance(120)).toBe(120)
  })

  it('is per mile in imperial, since a mile is further', () => {
    // Left unconverted, the CO2 tile read g/km whichever system was chosen —
    // the one figure on the page that ignored the switch entirely.
    const u = makeUnits('imperial')
    expect(u.co2Unit).toBe('g/mi')
    expect(u.co2PerDistance(120)).toBeCloseTo(193.12, 2)
  })

  it('has nothing to convert when there is nothing to show', () => {
    expect(makeUnits('imperial').co2PerDistance(null)).toBeNull()
    expect(makeUnits('metric').co2PerDistance(undefined)).toBeNull()
  })
})


describe('saying the same figure both ways', () => {
  it('leads with energy per hundred, whichever distance unit is chosen', () => {
    // The headline means the same thing in both systems; the familiar
    // inverted form sits beside it rather than replacing it.
    const metric = makeUnits('metric')
    expect(metric.efficiency(16)).toBe('16.00')
    expect(metric.efficiencyUnit).toBe('kWh/100km')

    const imperial = makeUnits('imperial')
    expect(imperial.efficiency(16)).toBe('25.75')      // per 100 miles
    expect(imperial.efficiencyUnit).toBe('kWh/100mi')
  })

  it('offers the inversion alongside, pointing the other way', () => {
    // 16 kWh/100km is 6.25 km per kWh, or 3.88 miles per kWh.
    expect(makeUnits('metric').efficiencyAlt(16)).toBe('6.25')
    expect(makeUnits('metric').efficiencyAltUnit).toBe('km/kWh')
    expect(makeUnits('imperial').efficiencyAlt(16)).toBe('3.88')
    expect(makeUnits('imperial').efficiencyAltUnit).toBe('mi/kWh')
  })

  it('does the same for fuel, in the two forms people actually quote', () => {
    expect(makeUnits('metric').consumptionAltUnit).toBe('mpg')
    expect(makeUnits('imperial').consumptionAltUnit).toBe('L/100km')
    // 7 L/100km is about 40.4 mpg imperial.
    expect(makeUnits('metric').consumptionAlt(7)).toBe('40.4')
    expect(makeUnits('imperial').consumptionAlt(7)).toBe('7.0')
  })

  it('has nothing to invert when there is nothing to show', () => {
    expect(makeUnits('imperial').efficiencyAlt(null)).toBe('—')
    expect(makeUnits('metric').consumptionAlt(undefined)).toBe('—')
  })
})
