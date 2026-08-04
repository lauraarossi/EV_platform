export type FuelType = 'electric' | 'petrol' | 'diesel' | 'hybrid'
export type ChargerType = 'ac_home' | 'ac_public' | 'dc_rapid' | 'dc_ultra'
export type DrivingMix = 'city' | 'mixed' | 'motorway'

export interface Vehicle {
  id: number
  make: string
  model: string
  trim?: string | null
  year: number
  fuel_type: FuelType
  nickname?: string | null
  image_url?: string | null
  battery_capacity_kwh?: number | null
  onboard_charger_kw?: number | null
  wltp_range_km?: number | null
  engine_size_cc?: number | null
  fuel_consumption_l_per_100km?: number | null
  horsepower?: number | null
  zero_to_100_seconds?: number | null
  top_speed_kmh?: number | null
  kerb_weight_kg?: number | null
  is_comparison_vehicle: boolean
}

export type VehicleInput = Omit<Vehicle, 'id'>

export interface ChargingSession {
  id: number
  vehicle_id: number
  date: string
  time_of_day?: string | null
  odometer_km: number
  kwh_added: number
  cost?: number | null
  currency: string
  soc_start_pct?: number | null
  soc_end_pct?: number | null
  charger_type: ChargerType
  charger_capacity_kw?: number | null
  location_city?: string | null
  country: string
  driving_mix?: DrivingMix | null
  notes?: string | null
}

export type ChargingSessionInput = Omit<ChargingSession, 'id'>

/** The driving between two consecutive charges. Derived server-side. */
export interface Interval {
  from_session_id: number
  to_session_id: number
  start_date: string
  end_date: string
  distance_km: number
  kwh_added: number
  cost: number | null
  energy_used_kwh: number | null
  /** false when energy was approximated from kWh added rather than SoC. */
  energy_is_exact: boolean
  efficiency_kwh_per_100km: number | null
  cost_per_100km: number | null
  driving_mix: DrivingMix | null
  location_city: string | null
}

export interface Summary {
  session_count: number
  interval_count: number
  total_distance_km: number
  total_kwh_added: number
  total_cost: number
  total_energy_used_kwh: number | null
  energy_is_exact: boolean
  avg_efficiency_kwh_per_100km: number | null
  avg_cost_per_100km: number | null
  avg_price_per_kwh: number | null
  latest_odometer_km: number | null
  anomalies: string[]
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
