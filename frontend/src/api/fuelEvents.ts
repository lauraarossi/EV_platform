import api from './client'
import type { FuelEvent, FuelEventInput } from '../types'

export const getFuelEvents = (vehicleId?: number) =>
  api
    .get<FuelEvent[]>('/fuel-events/', { params: vehicleId ? { vehicle_id: vehicleId } : {} })
    .then(r => r.data)

export const createFuelEvent = (data: FuelEventInput) =>
  api.post<FuelEvent>('/fuel-events/', data).then(r => r.data)

export const updateFuelEvent = (id: number, data: FuelEventInput) =>
  api.put<FuelEvent>(`/fuel-events/${id}`, data).then(r => r.data)

export const deleteFuelEvent = (id: number) => api.delete(`/fuel-events/${id}`)
