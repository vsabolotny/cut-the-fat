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
  'Housing', 'Groceries', 'Dining', 'Transportation', 'Entertainment',
  'Health', 'Shopping', 'Subscriptions', 'Travel', 'Education',
  'Utilities', 'Insurance', 'Income', 'Transfers', 'Other',
]

export const CATEGORY_COLORS: Record<string, string> = {
  Housing: '#6366f1',
  Groceries: '#22c55e',
  Dining: '#f97316',
  Transportation: '#3b82f6',
  Entertainment: '#a855f7',
  Health: '#ec4899',
  Shopping: '#eab308',
  Subscriptions: '#14b8a6',
  Travel: '#06b6d4',
  Education: '#8b5cf6',
  Utilities: '#64748b',
  Insurance: '#78716c',
  Income: '#10b981',
  Transfers: '#94a3b8',
  Other: '#9ca3af',
}
