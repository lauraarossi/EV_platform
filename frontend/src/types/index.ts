export type FuelType = 'electric' | 'petrol' | 'diesel' | 'hybrid'
export type Transmission = 'single_speed' | 'manual' | 'automatic' | 'cvt' | 'dual_clutch'

export const TRANSMISSION_LABEL: Record<Transmission, string> = {
  single_speed: 'Single-speed',
  manual: 'Manual',
  automatic: 'Automatic',
  cvt: 'CVT',
  dual_clutch: 'Dual-clutch',
}
export type ChargerType = 'ac_home' | 'ac_public' | 'dc_rapid' | 'dc_ultra'
export type DrivingMix = 'city' | 'mixed' | 'motorway'

export interface Vehicle {
  id: number
  make: string
  model: string
  trim?: string | null
  year: number
  fuel_type: FuelType
  transmission?: Transmission | null
  nickname?: string | null
  image_url?: string | null
  battery_capacity_kwh?: number | null
  onboard_charger_kw?: number | null
  wltp_range_km?: number | null
  consumption_kwh_per_100km?: number | null
  engine_size_cc?: number | null
  tank_capacity_litres?: number | null
  fuel_consumption_l_per_100km?: number | null
  horsepower?: number | null
  zero_to_100_seconds?: number | null
  top_speed_kmh?: number | null
  kerb_weight_kg?: number | null
  is_comparison_vehicle: boolean
}

export type VehicleInput = Omit<Vehicle, 'id'>

/**
 * One refuelling: a charge, a tank of petrol, or both at once for a plug-in
 * hybrid. What went in is always recorded; the level either side is optional
 * and is what makes the interval's consumption exact rather than approximate.
 */
export interface FuelEvent {
  id: number
  vehicle_id: number
  date: string
  time_of_day?: string | null
  odometer_km: number
  energy_kwh?: number | null
  volume_litres?: number | null
  cost?: number | null
  currency: string
  soc_start_pct?: number | null
  soc_end_pct?: number | null
  tank_start_pct?: number | null
  tank_end_pct?: number | null
  charger_type?: ChargerType | null
  charger_capacity_kw?: number | null
  location_city?: string | null
  country: string
  driving_mix?: DrivingMix | null
  notes?: string | null
}

export type FuelEventInput = Omit<FuelEvent, 'id'>

/** The driving between two consecutive fills. Derived server-side. */
export interface Interval {
  from_event_id: number
  to_event_id: number
  start_date: string
  end_date: string
  distance_km: number
  cost: number | null

  energy_added_kwh: number | null
  energy_used_kwh: number | null
  /** false when energy was approximated from what went in rather than SoC. */
  energy_is_exact: boolean
  efficiency_kwh_per_100km: number | null

  volume_added_litres: number | null
  volume_used_litres: number | null
  volume_is_exact: boolean
  consumption_l_per_100km: number | null

  /** Burning the fuel and generating the electricity — not the full lifecycle. */
  co2_g: number | null
  co2_g_per_km: number | null

  cost_per_100km: number | null
  driving_mix: DrivingMix | null
  location_city: string | null
}

export interface Summary {
  event_count: number
  interval_count: number
  total_distance_km: number
  total_cost: number

  total_energy_added_kwh: number
  total_energy_used_kwh: number | null
  energy_is_exact: boolean
  avg_efficiency_kwh_per_100km: number | null
  avg_price_per_kwh: number | null

  total_volume_added_litres: number
  total_volume_used_litres: number | null
  volume_is_exact: boolean
  avg_consumption_l_per_100km: number | null
  avg_price_per_litre: number | null

  total_co2_kg: number | null
  avg_co2_g_per_km: number | null

  avg_cost_per_100km: number | null
  latest_odometer_km: number | null
  anomalies: string[]
}

/** A reference specification used to prefill a vehicle you own. */
export interface CatalogVehicle {
  id: string
  source: 'evdb' | 'manual'
  source_name: string | null
  source_url: string | null
  licence: string | null
  make: string
  model: string
  variant: string
  trim: string | null
  model_year: number | null
  fuel_type: FuelType
  transmission: Transmission | null
  battery_capacity_kwh: number | null
  battery_usable_kwh: number | null
  onboard_charger_kw: number | null
  dc_charge_power_kw: number | null
  wltp_range_km: number | null
  consumption_wltp_kwh_100km: number | null
  consumption_real_world_kwh_100km: number | null
  engine_size_cc: number | null
  fuel_consumption_l_per_100km: number | null
  horsepower: number | null
  zero_to_100_seconds: number | null
  top_speed_kmh: number | null
  kerb_weight_kg: number | null
  body_style: string | null
  image_url: string | null
  data_quality: string | null
}

/**
 * The three catalogue sources each spell a car their own way, so the API
 * groups them: `make`/`model` are the spelling to show, and the `_key` fields
 * identify the group and are what to send back.
 */
export interface CatalogMake {
  make: string
  make_key: string
  model_count: number
}

export interface CatalogModel {
  make_key: string
  model: string
  model_key: string
  variant_count: number
}

/** One interval of driving, costed at the rate that applied at the time. */
export interface PricedInterval {
  start_date: string
  end_date: string
  distance_km: number
  /** Litres or kWh, per the comparison car's fuel — see Comparison.unit. */
  quantity: number
  unit_price: number | null
  cost: number | null
  price_as_of: string | null
  price_is_estimate: boolean
}

/**
 * What the same driving would have cost in another car. Symmetric: the
 * comparison may be petrol, diesel or electric, whichever you drive.
 */
export interface Comparison {
  distance_km: number
  vehicle: string
  actual_cost: number
  alternative_cost: number
  /** Positive means the alternative would have cost more — you are ahead. */
  saving: number
  actual_cost_per_100km: number | null
  alternative_cost_per_100km: number | null
  actual_co2_kg: number | null
  alternative_co2_kg: number
  /** Positive means the alternative would have emitted more. */
  co2_saving_kg: number
  actual_co2_g_per_km: number | null
  alternative_co2_g_per_km: number | null
  grid_co2_g_per_kwh: number
  quantity: number
  unit: 'litres' | 'kwh'
  unit_label: string
  basis: number
  basis_label: string
  comparison_vehicle: string
  comparison_fuel: FuelType
  used_fallback_price: boolean
  unpriced_intervals: number
  intervals: PricedInterval[]
}

export const CHARGER_LABEL: Record<ChargerType, string> = {
  ac_home: 'Home AC',
  ac_public: 'Public AC',
  dc_rapid: 'DC rapid',
  dc_ultra: 'DC ultra',
}

export const DRIVING_MIX_LABEL: Record<DrivingMix, string> = {
  city: 'City',
  mixed: 'Mixed',
  motorway: 'Motorway',
}
