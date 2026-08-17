import api from './client'
import type { CatalogMake, CatalogModel, CatalogVehicle, FuelType } from '../types'

export const getMakes = (fuelType?: FuelType) =>
  api
    .get<CatalogMake[]>('/catalog/makes', { params: fuelType ? { fuel_type: fuelType } : {} })
    .then(r => r.data)

export const getModels = (makeKey: string, fuelType?: FuelType) =>
  api
    .get<CatalogModel[]>('/catalog/models', {
      params: { make_key: makeKey, ...(fuelType ? { fuel_type: fuelType } : {}) },
    })
    .then(r => r.data)

export const getVariants = (makeKey: string, modelKey: string) =>
  api
    .get<CatalogVehicle[]>('/catalog/variants', {
      params: { make_key: makeKey, model_key: modelKey },
    })
    .then(r => r.data)

export interface RegLookup {
  registration: string
  valid: boolean
  year: number | null
  half: number | null
  county: string | null
  county_code: string | null
  make: string | null
  model: string | null
  notes: string[]
}

export const lookupRegistration = (reg: string) =>
  api.get<RegLookup>('/catalog/lookup/registration', { params: { reg } }).then(r => r.data)
