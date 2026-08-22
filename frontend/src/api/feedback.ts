import api from './client'

export type FeedbackStatus = 'new' | 'read' | 'done'

export interface Feedback {
  id: number
  message: string
  page: string | null
  user_agent: string | null
  user_id: number | null
  email: string | null
  status: FeedbackStatus
  created_at: string
}

/** Open to anyone — no account needed, which is rather the point. */
export const sendFeedback = (message: string, page: string, email?: string) =>
  api.post('/feedback/', { message, page, email: email || null }).then(r => r.data)

export const getFeedback = (status?: FeedbackStatus) =>
  api.get<Feedback[]>('/admin/feedback', { params: status ? { status } : {} }).then(r => r.data)

export const setFeedbackStatus = (id: number, status: FeedbackStatus) =>
  api.patch<Feedback>(`/admin/feedback/${id}`, { status }).then(r => r.data)
