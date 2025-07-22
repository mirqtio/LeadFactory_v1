/**
 * AppShell Component
 * Main application shell that provides consistent layout and navigation
 */
import React, { useState, useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import Navigation from '@/components/navigation/Navigation'
import AuthGuard from '@/components/auth/AuthGuard'
import useAuthStore from '@/store/authStore'
import useThemeStore from '@/store/themeStore'
import type { Role } from '@/types'

interface AppShellProps {
  requireAuth?: boolean
  allowedRoles?: Role[]
  showNavigation?: boolean
}

/**
 * AppShell provides the main application layout with navigation and authentication
 */
export default function AppShell({ 
  requireAuth = true, 
  allowedRoles = [], 
  showNavigation = true 
}: AppShellProps) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const { checkAuth, isLoading } = useAuthStore()
  const { isDarkMode } = useThemeStore()

  // Check authentication on mount
  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  // Handle mobile menu toggle
  const handleMobileMenuToggle = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen)
  }

  // Close mobile menu when clicking outside or on route change
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 768) {
        setIsMobileMenuOpen(false)
      }
    }

    const handleRouteChange = () => {
      setIsMobileMenuOpen(false)
    }

    window.addEventListener('resize', handleResize)
    window.addEventListener('popstate', handleRouteChange)

    return () => {
      window.removeEventListener('resize', handleResize)
      window.removeEventListener('popstate', handleRouteChange)
    }
  }, [])

  // Show loading screen during initial auth check
  if (isLoading) {
    return (
      <div className="min-h-screen bg-neutral-50 dark:bg-neutral-900 flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-synthesis-blue mx-auto"></div>
          <p className="text-neutral-600 dark:text-neutral-400">Loading application...</p>
        </div>
      </div>
    )
  }

  const shellContent = (
    <div className={`min-h-screen bg-neutral-50 dark:bg-neutral-900 ${isDarkMode ? 'dark' : ''}`}>
      {/* Navigation */}
      {showNavigation && (
        <Navigation 
          onMobileMenuToggle={handleMobileMenuToggle}
          isMobileMenuOpen={isMobileMenuOpen}
        />
      )}

      {/* Main content area */}
      <main className={showNavigation ? 'pt-0' : 'pt-16'}>
        {/* Mobile menu overlay */}
        {isMobileMenuOpen && (
          <div 
            className="fixed inset-0 bg-black bg-opacity-50 z-40 md:hidden"
            onClick={handleMobileMenuToggle}
            aria-hidden="true"
          />
        )}

        {/* Page content */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Outlet />
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white dark:bg-neutral-900 border-t border-neutral-200 dark:border-neutral-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
            <div className="flex items-center space-x-2">
              <span className="text-2xl">🏭</span>
              <span className="text-sm text-neutral-600 dark:text-neutral-400">
                © 2024 LeadFactory. All rights reserved.
              </span>
            </div>
            <div className="flex items-center space-x-6 text-sm">
              <a 
                href="/privacy" 
                className="text-neutral-600 hover:text-synthesis-blue dark:text-neutral-400 dark:hover:text-synthesis-blue"
              >
                Privacy Policy
              </a>
              <a 
                href="/terms" 
                className="text-neutral-600 hover:text-synthesis-blue dark:text-neutral-400 dark:hover:text-synthesis-blue"
              >
                Terms of Service
              </a>
              <a 
                href="/support" 
                className="text-neutral-600 hover:text-synthesis-blue dark:text-neutral-400 dark:hover:text-synthesis-blue"
              >
                Support
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )

  // Apply authentication guard if required
  if (requireAuth) {
    return (
      <AuthGuard 
        requireAuth={requireAuth} 
        roles={allowedRoles}
      >
        {shellContent}
      </AuthGuard>
    )
  }

  return shellContent
}

/**
 * Specialized AppShell variants for different use cases
 */

/**
 * Public pages (landing, login, etc.) - no authentication required
 */
export function PublicShell({ children }: { children?: React.ReactNode }) {
  return (
    <AppShell 
      requireAuth={false} 
      showNavigation={true}
    >
      {children}
    </AppShell>
  )
}

/**
 * Authenticated pages - requires login but no specific roles
 */
export function AuthenticatedShell({ children }: { children?: React.ReactNode }) {
  return (
    <AppShell 
      requireAuth={true} 
      allowedRoles={[]}
      showNavigation={true}
    >
      {children}
    </AppShell>
  )
}

/**
 * Admin pages - requires admin role
 */
export function AdminShell({ children }: { children?: React.ReactNode }) {
  return (
    <AppShell 
      requireAuth={true} 
      allowedRoles={['ADMIN', 'SUPER_ADMIN']}
      showNavigation={true}
    >
      {children}
    </AppShell>
  )
}

/**
 * Full-screen layout - no navigation, just content area
 */
export function FullScreenShell({ 
  children, 
  requireAuth = true, 
  allowedRoles = [] 
}: { 
  children?: React.ReactNode
  requireAuth?: boolean
  allowedRoles?: Role[]
}) {
  return (
    <AppShell 
      requireAuth={requireAuth} 
      allowedRoles={allowedRoles}
      showNavigation={false}
    >
      {children}
    </AppShell>
  )
}