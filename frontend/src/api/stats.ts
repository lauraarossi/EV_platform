import api from './client'
import type { Interval, Summary } from '../types'

export const getSummary = (vehicleId: number) =>
  api.get<Summary>(`/stats/vehicles/${vehicleId}/summary`).then(r => r.data)

export const getIntervals = (vehicleId: number) =>
  api
    .get<{ intervals: Interval[]; anomalies: string[] }>(`/stats/vehicles/${vehicleId}/intervals`)
    .then(r => r.data)
