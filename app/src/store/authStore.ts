/**
 * Authentication Store using Zustand
 * Integrates with P0-026 authentication system
 */
import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import type { AuthState, User, Role } from '@/types'
import { authApi } from '@/api/client'

interface AuthActions {
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
  refreshToken: () => Promise<void>
  setLoading: (loading: boolean) => void
  setUser: (user: User | null) => void
  setToken: (token: string | null) => void
  getUserRole: () => Role | null
}

type AuthStore = AuthState & AuthActions

const useAuthStore = create<AuthStore>()(
  devtools(
    persist(
      (set, get) => ({
        // State
        user: null,
        isAuthenticated: false,
        isLoading: false,
        token: null,

        // Actions
        login: async (email: string, password: string) => {
          set({ isLoading: true })
          try {
            const response = await authApi.login(email, password)
            
            if (response.success && response.data) {
              const { user, token } = response.data
              
              // Store token in localStorage
              localStorage.setItem('auth_token', token)
              
              set({
                user,
                token,
                isAuthenticated: true,
                isLoading: false,
              })
            } else {
              throw new Error(response.error?.message || 'Login failed')
            }
          } catch (error) {
            set({ isLoading: false })
            throw error
          }
        },

        logout: () => {
          // Clear localStorage
          localStorage.removeItem('auth_token')
          
          // Reset state
          set({
            user: null,
            token: null,
            isAuthenticated: false,
            isLoading: false,
          })
          
          // Call logout API (don't wait for response)
          authApi.logout().catch(() => {
            // Ignore logout API errors
          })
        },

        checkAuth: async () => {
          const token = localStorage.getItem('auth_token')
          
          if (!token) {
            set({ isAuthenticated: false, user: null })
            return
          }

          set({ isLoading: true })
          
          try {
            const response = await authApi.getCurrentUser()
            
            if (response.success && response.data) {
              set({
                user: response.data,
                token,
                isAuthenticated: true,
                isLoading: false,
              })
            } else {
              // Invalid token
              get().logout()
            }
          } catch (error) {
            // Auth check failed
            get().logout()
          }
        },

        refreshToken: async () => {
          try {
            const response = await authApi.refreshToken()
            
            if (response.success && response.data) {
              const { token } = response.data
              localStorage.setItem('auth_token', token)
              set({ token })
            } else {
              // Refresh failed, logout user
              get().logout()
            }
          } catch (error) {
            // Refresh failed, logout user
            get().logout()
          }
        },

        setLoading: (loading: boolean) => set({ isLoading: loading }),
        
        setUser: (user: User | null) => set({ 
          user, 
          isAuthenticated: user !== null 
        }),
        
        setToken: (token: string | null) => {
          if (token) {
            localStorage.setItem('auth_token', token)
          } else {
            localStorage.removeItem('auth_token')
          }
          set({ token })
        },

        getUserRole: (): Role | null => {
          const user = get().user
          if (!user) return null
          
          // In production, this would come from the user object or a separate API call
          // For now, derive from user properties or default to VIEWER
          // This would be replaced with actual role data from P0-026 RBAC system
          return 'VIEWER' // Placeholder
        },
      }),
      {
        name: 'auth-storage',
        partialize: (state) => ({
          token: state.token,
          user: state.user,
          isAuthenticated: state.isAuthenticated,
        }),
      }
    ),
    { name: 'authStore' }
  )
)

// Listen for auth events from other parts of the app
window.addEventListener('auth:logout', () => {
  useAuthStore.getState().logout()
})

export default useAuthStore