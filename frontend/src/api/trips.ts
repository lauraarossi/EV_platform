import api from './client'
import type { Trip } from '../types'

export const getTrips = (vehicleId?: number) =>
  api.get<Trip[]>('/trips', { params: vehicleId ? { vehicle_id: vehicleId } : {} }).then(r => r.data)
export const getTrip = (id: number) => api.get<Trip>(`/trips/${id}`).then(r => r.data)
export const createTrip = (data: Omit<Trip, 'id'>) => api.post<Trip>('/trips', data).then(r => r.data)
export const updateTrip = (id: number, data: Omit<Trip, 'id'>) => api.put<Trip>(`/trips/${id}`, data).then(r => r.data)
export const deleteTrip = (id: number) => api.delete(`/trips/${id}`)
