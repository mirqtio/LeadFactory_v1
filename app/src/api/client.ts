/**
 * API Client for Global Navigation Shell
 * Integrates with P0-026 authentication system
 */
import axios, { AxiosInstance, AxiosError } from 'axios'
import type { User, LoginRequest, AuthTokenResponse, RefreshTokenRequest } from '@/types'

// Create axios instance with base configuration
const apiClient: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling and token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config

    // Handle 401 unauthorized errors
    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true

      // Clear invalid token
      localStorage.removeItem('auth_token')
      
      // Redirect to login or emit auth event
      window.dispatchEvent(new CustomEvent('auth:logout'))
      
      return Promise.reject(error)
    }

    return Promise.reject(error)
  }
)

// Auth API methods - matching P0-026 endpoints
export const authApi = {
  /**
   * Verify current authentication status
   */
  async getCurrentUser(): Promise<User> {
    const response = await apiClient.get('/account/me')
    return response.data
  },

  /**
   * Login with credentials  
   */
  async login(email: string, password: string, deviceId?: string): Promise<AuthTokenResponse> {
    const loginData: LoginRequest = { email, password }
    if (deviceId) {
      loginData.device_id = deviceId
    }
    
    const response = await apiClient.post('/account/login', loginData)
    return response.data
  },

  /**
   * Logout current user
   */
  async logout(): Promise<{ message: string }> {
    const response = await apiClient.post('/account/logout')
    return response.data
  },

  /**
   * Refresh authentication token
   */
  async refreshToken(refreshToken: string): Promise<AuthTokenResponse> {
    const refreshData: RefreshTokenRequest = { refresh_token: refreshToken }
    const response = await apiClient.post('/account/refresh', refreshData)
    return response.data
  },
}

// Navigation API methods
export const navigationApi = {
  /**
   * Get user's navigation menu items based on role/permissions
   */
  async getNavigation(): Promise<ApiResponse<any[]>> {
    const response = await apiClient.get('/navigation')
    return response.data
  },
}

// Health check API
export const healthApi = {
  /**
   * Check API health status
   */
  async checkHealth(): Promise<ApiResponse<{ status: string; timestamp: string }>> {
    const response = await apiClient.get('/health')
    return response.data
  },
}

export default apiClient