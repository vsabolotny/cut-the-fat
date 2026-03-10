import { api } from './client'

export interface Insight {
  id: string
  text: string
  type: 'warning' | 'info' | 'success'
}

export interface InsightsResponse {
  insights: Insight[]
  generated_at: string | null
  cached: boolean
}

export const getInsights = (force = false) =>
  api.get<InsightsResponse>('/api/insights', { params: force ? { force: true } : {} })
