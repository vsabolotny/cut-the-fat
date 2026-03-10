import { api } from './client'

export interface CategoryTotal {
  category: string
  total: string
}

export interface MonthlySummary {
  month: string
  total: string
  categories: CategoryTotal[]
}

export interface ComparisonResponse {
  current_month: string
  previous_month: string
  current_total: string
  previous_total: string
  delta: string
  delta_pct: number | null
  category_deltas: Array<{
    category: string
    current: number
    previous: number
    delta: number
  }>
}

export interface HistoryResponse {
  months: string[]
  categories: string[]
  data: Record<string, number[]>
}

export const getSummary = (month?: string) =>
  api.get<MonthlySummary>('/api/dashboard/summary', { params: month ? { month } : {} })

export const getComparison = (month?: string) =>
  api.get<ComparisonResponse>('/api/dashboard/comparison', { params: month ? { month } : {} })

export const getHistory = (months?: number) =>
  api.get<HistoryResponse>('/api/dashboard/history', { params: months ? { months } : {} })
