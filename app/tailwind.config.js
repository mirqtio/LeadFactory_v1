/** @type {import('tailwindcss').Config} */
import designTokens from '../design/design_tokens.json'

// Transform design tokens into Tailwind theme configuration
const colors = {}
const spacing = {}
const fontSizes = {}

// Map primary colors
Object.entries(designTokens.colors.primary).forEach(([key, token]) => {
  colors[key.replace('-', '')] = token.value
})

// Map status colors  
Object.entries(designTokens.colors.status).forEach(([key, token]) => {
  colors[key] = token.value
})

// Map functional colors
Object.entries(designTokens.colors.functional).forEach(([key, token]) => {
  const name = key.replace('-', '')
  colors[name] = token.value
})

// Map spacing scale
Object.entries(designTokens.spacing.scale).forEach(([key, value]) => {
  spacing[key] = value
})

// Map typography scale
Object.entries(designTokens.typography.scale).forEach(([key, token]) => {
  fontSizes[key] = [token.size, { lineHeight: token.lineHeight, fontWeight: token.weight }]
})

export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Design token colors
        ...colors,
        // Additional semantic colors for better UX
        primary: {
          50: '#eff6ff',
          500: colors.synthesisblue,
          600: '#0052cc',
          700: '#004299',
        },
        gray: {
          50: colors.lightbg,
          100: '#f1f5f9',
          200: colors.border,
          500: colors.neutral,
          900: colors.anthracite,
        }
      },
      spacing: {
        ...spacing,
        // Additional spacing for UI components
        '18': '4.5rem',
        '88': '22rem',
      },
      fontSize: {
        ...fontSizes,
      },
      fontFamily: {
        sans: designTokens.typography.fontFamily.split(', '),
      },
      screens: {
        'mobile': designTokens.breakpoints.mobile,
        'tablet': designTokens.breakpoints.tablet, 
        'desktop': designTokens.breakpoints.desktop,
      },
      transitionDuration: {
        'micro': designTokens.animation.duration.micro,
        'standard': designTokens.animation.duration.standard,
        'page': designTokens.animation.duration.page,
        'data': designTokens.animation.duration.data,
      },
      transitionTimingFunction: {
        'out': designTokens.animation.easing.out,
        'in-out': designTokens.animation.easing['in-out'],
      },
      boxShadow: {
        'elevation-1': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
        'elevation-2': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        'elevation-3': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
      }
    },
  },
  plugins: [
    // Custom plugin to add design token CSS variables
    function({ addBase }) {
      addBase({
        ':root': {
          // CSS variables for runtime theme switching
          '--color-primary-anthracite': designTokens.colors.primary.anthracite.value,
          '--color-primary-white': designTokens.colors.primary.white.value,
          '--color-primary-synthesis-blue': designTokens.colors.primary['synthesis-blue'].value,
          '--color-status-critical': designTokens.colors.status.critical.value,
          '--color-status-warning': designTokens.colors.status.warning.value,
          '--color-status-success': designTokens.colors.status.success.value,
          '--color-functional-neutral': designTokens.colors.functional.neutral.value,
          '--color-functional-light-bg': designTokens.colors.functional['light-bg'].value,
          '--color-functional-border': designTokens.colors.functional.border.value,
          '--color-functional-dark-text': designTokens.colors.functional['dark-text'].value,
          '--spacing-base': designTokens.spacing.base,
          '--font-family': designTokens.typography.fontFamily,
        }
      })
    }
  ],
}