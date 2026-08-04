import api from './client'
import type { ChargingSession, ChargingSessionInput } from '../types'

export const getChargingSessions = (vehicleId?: number) =>
  api
    .get<ChargingSession[]>('/charging/', { params: vehicleId ? { vehicle_id: vehicleId } : {} })
    .then(r => r.data)

export const createChargingSession = (data: ChargingSessionInput) =>
  api.post<ChargingSession>('/charging/', data).then(r => r.data)

export const updateChargingSession = (id: number, data: ChargingSessionInput) =>
  api.put<ChargingSession>(`/charging/${id}`, data).then(r => r.data)

export const deleteChargingSession = (id: number) => api.delete(`/charging/${id}`)
