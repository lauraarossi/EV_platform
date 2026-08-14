import api from './client'

export interface AuthUser {
  id: number
  email: string
  display_name: string | null
  avatar_url: string | null
  has_password: boolean
  has_google: boolean
}

export interface AuthOptions {
  google_enabled: boolean
  registration_open: boolean
  google_client_id: string | null
}

export const getOptions = () => api.get<AuthOptions>('/auth/options').then(r => r.data)

export const getMe = () => api.get<AuthUser>('/auth/me').then(r => r.data)

export const login = (email: string, password: string) =>
  api.post<AuthUser>('/auth/login', { email, password }).then(r => r.data)

export const register = (email: string, password: string, display_name?: string) =>
  api.post<AuthUser>('/auth/register', { email, password, display_name }).then(r => r.data)

export const signInWithGoogle = (credential: string) =>
  api.post<AuthUser>('/auth/google', { credential }).then(r => r.data)

export const logout = () => api.post('/auth/logout')
