/**
 * Global Navigation Shell Type Definitions
 * Provides unified typing for the shell application
 */

// Authentication types based on P0-026 auth system
export interface User {
  id: string
  email: string
  organization_id?: string
  status: 'ACTIVE' | 'INACTIVE'
  created_at: string
  updated_at: string
}

export interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  token: string | null
}

// RBAC types from core/auth.py
export type Role = 
  | 'GUEST' 
  | 'VIEWER' 
  | 'SALES_REP' 
  | 'MARKETING_USER' 
  | 'ANALYST' 
  | 'TEAM_LEAD' 
  | 'MANAGER' 
  | 'ADMIN' 
  | 'SUPER_ADMIN'

export type Permission = 'READ' | 'CREATE' | 'UPDATE' | 'DELETE'

export type Resource = 
  | 'DASHBOARD' 
  | 'REPORTS' 
  | 'CAMPAIGNS' 
  | 'ANALYTICS' 
  | 'ADMIN'

// Navigation types
export interface NavigationItem {
  id: string
  label: string
  href: string
  icon?: string
  roles?: Role[]
  permissions?: { permission: Permission; resource?: Resource }[]
  children?: NavigationItem[]
  external?: boolean
}

// Theme types based on P0-020 design tokens
export interface DesignTokens {
  colors: {
    primary: Record<string, { value: string; usage: string; contrast?: Record<string, string> }>
    status: Record<string, { value: string; usage: string }>
    functional: Record<string, { value: string; usage: string; contrast?: Record<string, string> }>
  }
  typography: {
    fontFamily: string
    scale: Record<string, { size: string; weight: string; lineHeight: string }>
  }
  spacing: {
    base: string
    scale: Record<string, string>
  }
  animation: {
    duration: Record<string, string>
    easing: Record<string, string>
  }
  breakpoints: Record<string, string>
}

export interface ThemeState {
  isDarkMode: boolean
  tokens: DesignTokens
}

// Route types for lazy loading
export interface RouteConfig {
  path: string
  label: string
  component: React.LazyExoticComponent<React.ComponentType>
  roles?: Role[]
  permissions?: { permission: Permission; resource?: Resource }[]
}

// Shell configuration
export interface ShellConfig {
  appTitle: string
  navigation: NavigationItem[]
  routes: RouteConfig[]
  features: {
    darkMode: boolean
    breadcrumbs: boolean
    notifications: boolean
  }
}

// API types
export interface ApiError {
  message: string
  code: string
  details?: Record<string, unknown>
}

export interface ApiResponse<T = unknown> {
  data: T
  success: boolean
  error?: ApiError
}

// Component props types
export interface BaseComponentProps {
  className?: string
  children?: React.ReactNode
  testId?: string
}

// Mobile navigation state
export interface MobileNavState {
  isOpen: boolean
  activeSubmenu: string | null
}

// Loading states
export type LoadingState = 'idle' | 'loading' | 'success' | 'error'

export interface AsyncState<T> {
  data: T | null
  status: LoadingState
  error: string | null
}