import { api } from './client'

export interface Transaction {
  id: number
  upload_id: number
  date: string
  merchant: string
  merchant_normalized: string
  description: string
  amount: string
  type: string
  category: string
  category_source: string
}

export interface TransactionList {
  items: Transaction[]
  total: number
}

export interface TransactionFilters {
  month?: string
  category?: string
  search?: string
  type?: string
  limit?: number
  offset?: number
}

export const getTransactions = (filters: TransactionFilters = {}) =>
  api.get<TransactionList>('/api/transactions', { params: filters })

export const updateCategory = (id: number, category: string) =>
  api.patch<Transaction>(`/api/transactions/${id}/category`, { category })

export const CATEGORIES = [
  'Wohnen', 'Lebensmittel', 'Essen & Trinken', 'Verkehr', 'Freizeit',
  'Gesundheit', 'Einkaufen', 'Abonnements', 'Reisen', 'Bildung',
  'Haushalt', 'Versicherungen', 'Einnahmen', 'Umbuchungen', 'Sonstiges',
]

export const CATEGORY_COLORS: Record<string, string> = {
  'Wohnen': '#6366f1',
  'Lebensmittel': '#22c55e',
  'Essen & Trinken': '#f97316',
  'Verkehr': '#3b82f6',
  'Freizeit': '#a855f7',
  'Gesundheit': '#ec4899',
  'Einkaufen': '#eab308',
  'Abonnements': '#14b8a6',
  'Reisen': '#06b6d4',
  'Bildung': '#8b5cf6',
  'Haushalt': '#64748b',
  'Versicherungen': '#78716c',
  'Einnahmen': '#10b981',
  'Umbuchungen': '#94a3b8',
  'Sonstiges': '#9ca3af',
}
