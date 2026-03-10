import { api } from './client'

export const login = (password: string) =>
  api.post<{ token: string }>('/api/auth/login', { password })
