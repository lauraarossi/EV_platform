import api from './client'
import type { Comparison, Interval, Summary } from '../types'

export const getSummary = (vehicleId: number) =>
  api.get<Summary>(`/stats/vehicles/${vehicleId}/summary`).then(r => r.data)

export const getIntervals = (vehicleId: number) =>
  api
    .get<{ intervals: Interval[]; anomalies: string[] }>(`/stats/vehicles/${vehicleId}/intervals`)
    .then(r => r.data)

export const getComparison = (
  vehicleId: number,
  comparisonVehicleId: number,
  fallback?: { perLitre?: number; perKwh?: number },
  /** 0 = your car as entered, 1 = as your log actually measured it. */
  measuredWeight = 0,
) =>
  api
    .get<Comparison>(`/stats/vehicles/${vehicleId}/compare`, {
      params: {
        comparison_vehicle_id: comparisonVehicleId,
        ...(fallback?.perLitre != null ? { fallback_price_per_litre: fallback.perLitre } : {}),
        ...(fallback?.perKwh != null ? { fallback_price_per_kwh: fallback.perKwh } : {}),
        ...(measuredWeight > 0 ? { measured_weight: measuredWeight } : {}),
      },
    })
    .then(r => r.data)
