export type FuelType = 'electric' | 'petrol' | 'diesel' | 'hybrid'

export type ChargerType = 'ac_home' | 'ac_public' | 'dc_rapid' | 'dc_ultra'

export interface Vehicle {
  id: number
  make: string
  model: string
  trim?: string
  year: number
  fuel_type: FuelType
  battery_capacity_kwh?: number
  onboard_charger_kw?: number
  wltp_range_km?: number
  engine_size_cc?: number
  fuel_consumption_l_per_100km?: number
  horsepower?: number
  zero_to_100_seconds?: number
  top_speed_kmh?: number
  kerb_weight_kg?: number
  is_comparison_vehicle: boolean
}

export interface Trip {
  id: number
  vehicle_id: number
  date: string
  distance_km: number
  average_speed_kmh?: number
  origin_city?: string
  destination_city?: string
  country: string
  notes?: string
}

export interface ChargingSession {
  id: number
  vehicle_id: number
  trip_id?: number
  date: string
  time_of_day?: string
  kwh_charged: number
  cost?: number
  currency: string
  charger_type: ChargerType
  charger_capacity_kw?: number
  location_city?: string
  country: string
}
