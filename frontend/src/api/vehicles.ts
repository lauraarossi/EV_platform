import api from './client'
import type { Vehicle } from '../types'

export const getVehicles = () => api.get<Vehicle[]>('/vehicles').then(r => r.data)
export const getVehicle = (id: number) => api.get<Vehicle>(`/vehicles/${id}`).then(r => r.data)
export const createVehicle = (data: Omit<Vehicle, 'id'>) => api.post<Vehicle>('/vehicles', data).then(r => r.data)
export const updateVehicle = (id: number, data: Omit<Vehicle, 'id'>) => api.put<Vehicle>(`/vehicles/${id}`, data).then(r => r.data)
export const deleteVehicle = (id: number) => api.delete(`/vehicles/${id}`)
