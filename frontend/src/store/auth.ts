import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api } from '../api/client'

interface AuthState {
  token: string | null
  setToken: (token: string) => void
  logout: () => void
  verify: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      setToken: (token) => {
        set({ token })
        api.defaults.headers.common['Authorization'] = `Bearer ${token}`
      },
      logout: () => {
        set({ token: null })
        delete api.defaults.headers.common['Authorization']
      },
      verify: async () => {
        const token = get().token
        if (!token) return
        api.defaults.headers.common['Authorization'] = `Bearer ${token}`
        try {
          const res = await api.get('/api/auth/verify')
          if (!res.data.valid) get().logout()
        } catch {
          get().logout()
        }
      },
    }),
    {
      name: 'auth-store',
      onRehydrateStorage: () => (state) => {
        if (state?.token) {
          api.defaults.headers.common['Authorization'] = `Bearer ${state.token}`
        }
      },
    }
  )
)
