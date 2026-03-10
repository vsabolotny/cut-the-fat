import { api } from './client'

export interface Category {
  id: number
  name: string
  color: string
}

export const getCategories = () => api.get<Category[]>('/api/categories')
