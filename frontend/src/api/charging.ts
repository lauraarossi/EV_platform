import api from './client'
import type { ChargingSession } from '../types'

export const getChargingSessions = (vehicleId?: number) =>
  api.get<ChargingSession[]>('/charging', { params: vehicleId ? { vehicle_id: vehicleId } : {} }).then(r => r.data)
export const getChargingSession = (id: number) => api.get<ChargingSession>(`/charging/${id}`).then(r => r.data)
export const createChargingSession = (data: Omit<ChargingSession, 'id'>) => api.post<ChargingSession>('/charging', data).then(r => r.data)
export const updateChargingSession = (id: number, data: Omit<ChargingSession, 'id'>) => api.put<ChargingSession>(`/charging/${id}`, data).then(r => r.data)
export const deleteChargingSession = (id: number) => api.delete(`/charging/${id}`)
