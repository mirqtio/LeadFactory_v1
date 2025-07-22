/**
 * AuthGuard Component
 * Protects routes based on authentication and role requirements
 */
import React, { useEffect } from 'react'
import type { Role, User } from '@/types'
import useAuthStore from '@/store/authStore'
import { hasRole, hasAnyRole } from '@/utils'

interface AuthGuardProps {
  children: React.ReactNode
  requireAuth?: boolean
  roles?: Role[]
  fallback?: React.ReactNode
}

/**
 * AuthGuard component that protects routes based on authentication and roles
 */
export default function AuthGuard({ 
  children, 
  requireAuth = true, 
  roles = [], 
  fallback = <div>Access denied. Please check your permissions.</div> 
}: AuthGuardProps) {
  const { user, isAuthenticated, isLoading, checkAuth } = useAuthStore()

  // Check authentication on mount
  useEffect(() => {
    if (!isAuthenticated && !isLoading) {
      checkAuth()
    }
  }, [isAuthenticated, isLoading, checkAuth])

  // Show loading state while checking auth
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-synthesisblue"></div>
      </div>
    )
  }

  // Check if authentication is required
  if (requireAuth && !isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="card max-w-md mx-auto p-6 text-center">
          <h2 className="text-h3 mb-4">Authentication Required</h2>
          <p className="text-neutral mb-4">
            Please log in to access this page.
          </p>
          <button 
            onClick={() => window.location.href = '/login'}
            className="btn-primary"
          >
            Go to Login
          </button>
        </div>
      </div>
    )
  }

  // Check role requirements
  if (roles.length > 0 && user) {
    const userRole = useAuthStore.getState().getUserRole()
    
    if (!userRole || !hasAnyRole(userRole, roles)) {
      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="card max-w-md mx-auto p-6 text-center">
            <h2 className="text-h3 mb-4">Access Denied</h2>
            <p className="text-neutral mb-4">
              You don't have the required permissions to access this page.
            </p>
            <p className="text-sm text-neutral/70 mb-4">
              Required roles: {roles.join(', ')}
              {userRole && (
                <>
                  <br />
                  Your role: {userRole}
                </>
              )}
            </p>
            <button 
              onClick={() => window.history.back()}
              className="btn-secondary"
            >
              Go Back
            </button>
          </div>
        </div>
      )
    }
  }

  // Allow access if all checks pass
  return <>{children}</>
}