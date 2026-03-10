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

