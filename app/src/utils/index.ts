/**
 * Utility functions for the Global Navigation Shell
 */
import type { Role, Permission, Resource, User, NavigationItem } from '@/types'
import clsx, { ClassValue } from 'clsx'

/**
 * Utility for merging CSS classes with clsx
 */
export function cn(...inputs: ClassValue[]) {
  return clsx(inputs)
}

/**
 * Role hierarchy for RBAC evaluation
 * Based on core/auth.py role hierarchy
 */
const ROLE_HIERARCHY: Record<Role, number> = {
  GUEST: 0,
  VIEWER: 1,
  SALES_REP: 2,
  MARKETING_USER: 2,
  ANALYST: 3,
  TEAM_LEAD: 4,
  MANAGER: 5,
  ADMIN: 6,
  SUPER_ADMIN: 7,
}

/**
 * Check if user has required role or higher
 */
export function hasRole(userRole: Role, requiredRole: Role): boolean {
  const userLevel = ROLE_HIERARCHY[userRole] ?? 0
  const requiredLevel = ROLE_HIERARCHY[requiredRole] ?? 0
  return userLevel >= requiredLevel
}

/**
 * Check if user has any of the required roles
 */
export function hasAnyRole(userRole: Role, requiredRoles: Role[]): boolean {
  return requiredRoles.some(role => hasRole(userRole, role))
}

/**
 * Placeholder for permission checking (would integrate with actual RBAC system)
 * In production, this would call the backend API
 */
export function hasPermission(
  user: User, 
  permission: Permission, 
  resource?: Resource
): boolean {
  // This is a placeholder - in production this would:
  // 1. Call the RBAC service API
  // 2. Check user permissions from backend
  // 3. Handle resource-specific permissions
  
  // For now, basic role-based access
  // This matches the pattern in core/auth.py
  console.warn('hasPermission is a placeholder - implement actual RBAC integration')
  return true // Allow all for development
}

/**
 * Filter navigation items based on user's role and permissions
 */
export function filterNavigation(
  navigation: NavigationItem[], 
  user: User | null,
  userRole?: Role
): NavigationItem[] {
  if (!user || !userRole) return []

  return navigation.filter(item => {
    // Check role requirements
    if (item.roles && item.roles.length > 0) {
      if (!hasAnyRole(userRole, item.roles)) {
        return false
      }
    }

    // Check permission requirements
    if (item.permissions && item.permissions.length > 0) {
      const hasRequiredPermission = item.permissions.every(perm =>
        hasPermission(user, perm.permission, perm.resource)
      )
      if (!hasRequiredPermission) {
        return false
      }
    }

    // Recursively filter children
    if (item.children) {
      item.children = filterNavigation(item.children, user, userRole)
    }

    return true
  })
}

/**
 * Get initials from user email or name
 */
export function getUserInitials(user: User): string {
  const email = user.email || ''
  const parts = email.split('@')[0].split('.')
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase()
  }
  return email.substring(0, 2).toUpperCase()
}

/**
 * Format file size for bundle analysis
 */
export function formatBytes(bytes: number, decimals = 2): string {
  if (bytes === 0) return '0 Bytes'
  
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i]
}

/**
 * Debounce function for performance optimization
 */
export function debounce<T extends (...args: unknown[]) => void>(
  func: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout>
  
  return function(this: ThisParameterType<T>, ...args: Parameters<T>) {
    clearTimeout(timeoutId)
    timeoutId = setTimeout(() => func.apply(this, args), delay)
  }
}

/**
 * Generate a stable hash from a string (for consistent keys)
 */
export function hashString(str: string): string {
  let hash = 0
  if (str.length === 0) return hash.toString()
  
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash // Convert to 32bit integer
  }
  
  return Math.abs(hash).toString(36)
}

/**
 * Check if running in development mode
 */
export function isDevelopment(): boolean {
  return import.meta.env.MODE === 'development'
}

/**
 * Safe JSON parse with fallback
 */
export function safeJsonParse<T>(json: string, fallback: T): T {
  try {
    return JSON.parse(json)
  } catch {
    return fallback
  }
}

/**
 * Create an external link component props
 */
export function getExternalLinkProps() {
  return {
    target: '_blank',
    rel: 'noopener noreferrer'
  }
}