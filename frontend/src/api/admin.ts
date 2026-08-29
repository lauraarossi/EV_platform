import api from './client'

export type ImportStatus = 'running' | 'ok' | 'failed'
export type UserRole = 'user' | 'admin'

export interface ImportRun {
  id: number
  task: string
  status: ImportStatus
  started_at: string
  finished_at: string | null
  duration_ms: number | null
  result: Record<string, unknown> | null
  error: string | null
  triggered_by_id: number | null
}

export interface AdminTask {
  key: string
  label: string
  description: string
  /** Warns before starting one that walks six years of data over the network. */
  slow: boolean
  last_run: ImportRun | null
}

export interface CatalogueSourceStat {
  source: string
  entries: number
  with_trim: number
  with_battery: number
  with_consumption: number
}

export interface AdminOverview {
  catalogue_total: number
  catalogue_by_source: CatalogueSourceStat[]
  distinct_makes: number
  distinct_models: number
  users: number
  admins: number
  vehicles: number
  fuel_events: number
  fuel_prices: number
  tariffs: number
  feedback_new: number
  tasks: AdminTask[]
}

export interface AdminUser {
  id: number
  email: string
  display_name: string | null
  role: UserRole
  is_active: boolean
  created_at: string | null
  last_login_at: string | null
  vehicles: number
}

export const getOverview = () => api.get<AdminOverview>('/admin/overview').then(r => r.data)

export const runTask = (key: string, params?: Record<string, unknown>) =>
  api.post<ImportRun>(`/admin/tasks/${key}/run`, params ?? {}).then(r => r.data)

/** Everything, in the order the sources depend on each other. */
export const runAll = () =>
  api.post<{ started: string[] }>('/admin/tasks/run-all', {}).then(r => r.data)

export const getRuns = (limit = 25) =>
  api.get<ImportRun[]>('/admin/runs', { params: { limit } }).then(r => r.data)

/**
 * Import a VCA zip picked in the browser.
 *
 * Sent as the raw body rather than a multipart form — one file needs no
 * dependency on the server to parse it.
 */
export const uploadVca = (file: File) =>
  api
    .post<ImportRun>('/admin/tasks/vca/upload', file, {
      params: { filename: file.name },
      headers: { 'Content-Type': 'application/zip' },
    })
    .then(r => r.data)

/**
 * Give up on a run that is stuck.
 *
 * It stops nothing — a background task belongs to the web process and there is
 * no handle to interrupt it. What it does is stop believing the record, so the
 * task is no longer refused as already running.
 */
export const abandonRun = (id: number) =>
  api.post<ImportRun>(`/admin/runs/${id}/abandon`, {}).then(r => r.data)

export const getUsers = () => api.get<AdminUser[]>('/admin/users').then(r => r.data)

export const setUserRole = (id: number, role: UserRole) =>
  api.patch<AdminUser>(`/admin/users/${id}/role`, { role }).then(r => r.data)
