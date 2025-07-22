/**
 * Theme Store using Zustand
 * Manages theme state and design tokens integration
 */
import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import type { ThemeState, DesignTokens } from '@/types'

// Import design tokens
import designTokensJson from '@design/design_tokens.json'

interface ThemeActions {
  toggleDarkMode: () => void
  setDarkMode: (isDarkMode: boolean) => void
  getColorValue: (path: string) => string | undefined
  getSpacingValue: (scale: string) => string | undefined
  getTypographyValue: (scale: string) => { size: string; weight: string; lineHeight: string } | undefined
}

type ThemeStore = ThemeState & ThemeActions

const useThemeStore = create<ThemeStore>()(
  devtools(
    persist(
      (set, get) => ({
        // State
        isDarkMode: false,
        tokens: designTokensJson as DesignTokens,

        // Actions
        toggleDarkMode: () => {
          const newDarkMode = !get().isDarkMode
          set({ isDarkMode: newDarkMode })
          
          // Apply theme to document
          if (typeof document !== 'undefined') {
            document.documentElement.classList.toggle('dark', newDarkMode)
          }
        },

        setDarkMode: (isDarkMode: boolean) => {
          set({ isDarkMode })
          
          // Apply theme to document
          if (typeof document !== 'undefined') {
            document.documentElement.classList.toggle('dark', isDarkMode)
          }
        },

        getColorValue: (path: string) => {
          const tokens = get().tokens
          const pathParts = path.split('.')
          
          try {
            let current: any = tokens.colors
            for (const part of pathParts) {
              current = current[part]
            }
            return current?.value
          } catch {
            return undefined
          }
        },

        getSpacingValue: (scale: string) => {
          const tokens = get().tokens
          return tokens.spacing.scale[scale]
        },

        getTypographyValue: (scale: string) => {
          const tokens = get().tokens
          return tokens.typography.scale[scale]
        },
      }),
      {
        name: 'theme-storage',
        partialize: (state) => ({
          isDarkMode: state.isDarkMode,
        }),
      }
    ),
    { name: 'themeStore' }
  )
)

// Initialize theme on store creation
if (typeof document !== 'undefined') {
  const { isDarkMode } = useThemeStore.getState()
  document.documentElement.classList.toggle('dark', isDarkMode)
}

export default useThemeStore