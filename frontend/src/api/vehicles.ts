import api from './client'
import type { Vehicle, VehicleInput } from '../types'

export const getVehicles = () => api.get<Vehicle[]>('/vehicles/').then(r => r.data)
export const createVehicle = (data: VehicleInput) =>
  api.post<Vehicle>('/vehicles/', data).then(r => r.data)
export const updateVehicle = (id: number, data: VehicleInput) =>
  api.put<Vehicle>(`/vehicles/${id}`, data).then(r => r.data)
export const deleteVehicle = (id: number) => api.delete(`/vehicles/${id}`)
