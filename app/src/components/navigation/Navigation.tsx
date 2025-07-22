/**
 * Navigation Component
 * Main navigation bar with role-based menu items and user context
 */
import React, { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import useAuthStore from '@/store/authStore'
import useThemeStore from '@/store/themeStore'
import { hasRole } from '@/utils'
import type { NavigationItem, Role } from '@/types'

interface NavigationProps {
  onMobileMenuToggle?: () => void
  isMobileMenuOpen?: boolean
}

/**
 * Default navigation items with role-based access control
 */
const defaultNavItems: NavigationItem[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    href: '/dashboard',
    icon: '📊',
    requiredRoles: ['VIEWER', 'SALES_REP', 'MARKETING_USER', 'ANALYST', 'TEAM_LEAD', 'MANAGER', 'ADMIN', 'SUPER_ADMIN'],
    order: 1
  },
  {
    id: 'leads',
    label: 'Lead Management',
    href: '/leads',
    icon: '🎯',
    requiredRoles: ['SALES_REP', 'TEAM_LEAD', 'MANAGER', 'ADMIN', 'SUPER_ADMIN'],
    order: 2
  },
  {
    id: 'campaigns',
    label: 'Marketing Campaigns',
    href: '/campaigns',
    icon: '📢',
    requiredRoles: ['MARKETING_USER', 'TEAM_LEAD', 'MANAGER', 'ADMIN', 'SUPER_ADMIN'],
    order: 3
  },
  {
    id: 'analytics',
    label: 'Analytics',
    href: '/analytics',
    icon: '📈',
    requiredRoles: ['ANALYST', 'TEAM_LEAD', 'MANAGER', 'ADMIN', 'SUPER_ADMIN'],
    order: 4
  },
  {
    id: 'reports',
    label: 'Reports',
    href: '/reports',
    icon: '📋',
    requiredRoles: ['TEAM_LEAD', 'MANAGER', 'ADMIN', 'SUPER_ADMIN'],
    order: 5
  },
  {
    id: 'admin',
    label: 'Administration',
    href: '/admin',
    icon: '⚙️',
    requiredRoles: ['ADMIN', 'SUPER_ADMIN'],
    order: 6
  }
]

export default function Navigation({ onMobileMenuToggle, isMobileMenuOpen }: NavigationProps) {
  const location = useLocation()
  const { user, isAuthenticated, logout, getUserRole } = useAuthStore()
  const { isDarkMode, toggleDarkMode } = useThemeStore()
  const [navItems, setNavItems] = useState<NavigationItem[]>([])

  // Filter navigation items based on user role
  useEffect(() => {
    if (!isAuthenticated || !user) {
      setNavItems([])
      return
    }

    const userRole = getUserRole()
    if (!userRole) {
      setNavItems([])
      return
    }

    const filteredItems = defaultNavItems
      .filter(item => 
        !item.requiredRoles || 
        item.requiredRoles.some(role => hasRole(userRole, role as Role))
      )
      .sort((a, b) => a.order - b.order)

    setNavItems(filteredItems)
  }, [isAuthenticated, user, getUserRole])

  const handleLogout = () => {
    logout()
  }

  if (!isAuthenticated) {
    return (
      <nav className="bg-white dark:bg-neutral-900 border-b border-neutral-200 dark:border-neutral-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <Link to="/" className="flex items-center space-x-2">
                <span className="text-2xl">🏭</span>
                <span className="font-semibold text-xl text-synthesis-blue">
                  LeadFactory
                </span>
              </Link>
            </div>
            <div className="flex items-center space-x-4">
              <button
                onClick={toggleDarkMode}
                className="p-2 rounded-md text-neutral-600 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800"
                aria-label="Toggle dark mode"
              >
                {isDarkMode ? '☀️' : '🌙'}
              </button>
              <Link
                to="/login"
                className="btn-primary"
              >
                Sign In
              </Link>
            </div>
          </div>
        </div>
      </nav>
    )
  }

  return (
    <nav className="bg-white dark:bg-neutral-900 border-b border-neutral-200 dark:border-neutral-700">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          {/* Logo and main navigation */}
          <div className="flex">
            {/* Logo */}
            <div className="flex-shrink-0 flex items-center">
              <Link to="/dashboard" className="flex items-center space-x-2">
                <span className="text-2xl">🏭</span>
                <span className="font-semibold text-xl text-synthesis-blue">
                  LeadFactory
                </span>
              </Link>
            </div>

            {/* Desktop navigation */}
            <div className="hidden md:ml-6 md:flex md:space-x-8">
              {navItems.map((item) => {
                const isActive = location.pathname === item.href || 
                  (item.href !== '/dashboard' && location.pathname.startsWith(item.href))
                
                return (
                  <Link
                    key={item.id}
                    to={item.href}
                    className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                      isActive
                        ? 'border-synthesis-blue text-synthesis-blue'
                        : 'border-transparent text-neutral-500 hover:text-neutral-700 hover:border-neutral-300 dark:text-neutral-400 dark:hover:text-neutral-200'
                    }`}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    <span className="mr-2">{item.icon}</span>
                    {item.label}
                  </Link>
                )
              })}
            </div>
          </div>

          {/* Right side - user menu and theme toggle */}
          <div className="hidden md:ml-6 md:flex md:items-center md:space-x-4">
            {/* Theme toggle */}
            <button
              onClick={toggleDarkMode}
              className="p-2 rounded-md text-neutral-600 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800"
              aria-label="Toggle dark mode"
            >
              {isDarkMode ? '☀️' : '🌙'}
            </button>

            {/* User menu */}
            <div className="relative">
              <div className="flex items-center space-x-3">
                <span className="text-sm text-neutral-700 dark:text-neutral-300">
                  Welcome, {user?.name || user?.email}
                </span>
                <button
                  onClick={handleLogout}
                  className="btn-secondary"
                >
                  Sign Out
                </button>
              </div>
            </div>
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden flex items-center space-x-2">
            <button
              onClick={toggleDarkMode}
              className="p-2 rounded-md text-neutral-600 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800"
              aria-label="Toggle dark mode"
            >
              {isDarkMode ? '☀️' : '🌙'}
            </button>
            <button
              onClick={onMobileMenuToggle}
              className="p-2 rounded-md text-neutral-400 hover:text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800 focus:outline-none focus:ring-2 focus:ring-synthesis-blue"
              aria-expanded={isMobileMenuOpen}
              aria-label="Toggle navigation menu"
            >
              <span className="sr-only">Open main menu</span>
              {isMobileMenuOpen ? (
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      {isMobileMenuOpen && (
        <div className="md:hidden">
          <div className="pt-2 pb-3 space-y-1 sm:px-3">
            {navItems.map((item) => {
              const isActive = location.pathname === item.href || 
                (item.href !== '/dashboard' && location.pathname.startsWith(item.href))
              
              return (
                <Link
                  key={item.id}
                  to={item.href}
                  className={`block px-3 py-2 rounded-md text-base font-medium ${
                    isActive
                      ? 'text-synthesis-blue bg-synthesis-blue/10'
                      : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:text-neutral-100 dark:hover:bg-neutral-800'
                  }`}
                  aria-current={isActive ? 'page' : undefined}
                  onClick={onMobileMenuToggle}
                >
                  <span className="mr-2">{item.icon}</span>
                  {item.label}
                </Link>
              )
            })}
          </div>
          <div className="pt-4 pb-3 border-t border-neutral-200 dark:border-neutral-700">
            <div className="px-4 space-y-2">
              <div className="text-sm text-neutral-600 dark:text-neutral-400">
                Signed in as: {user?.name || user?.email}
              </div>
              <button
                onClick={handleLogout}
                className="block w-full text-left px-3 py-2 rounded-md text-base font-medium text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:text-neutral-100 dark:hover:bg-neutral-800"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}
    </nav>
  )
}