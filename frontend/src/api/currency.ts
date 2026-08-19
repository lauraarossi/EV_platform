import api from './client'

export interface CurrencyChoice {
  code: string
  symbol: string
}

export interface Rates {
  base: string
  /** Newest rate held per currency, keyed by code. Base is always 1. */
  rates: Record<string, number>
  choices: CurrencyChoice[]
  source: string
}

export const getRates = () => api.get<Rates>('/currency/').then(r => r.data)

export const setCurrency = (currency: string) =>
  api.put('/currency/', { currency }).then(r => r.data)
