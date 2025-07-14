# P0-027 - Global Navigation Shell
**Priority**: P0
**Status**: Not Started
**Estimated Effort**: 5 days
**Dependencies**: P0-026

## Goal & Success Criteria

### Goal
Create a unified React shell application that hosts all LeadFactory UI features with consistent navigation and authentication, enabling secure, scalable micro-frontend architecture with role-based access control.

### Business Value
- **Business value**: Consolidates fragmented UI components into cohesive user experience, reducing development friction and enabling independent team velocity
- **Integration**: Builds on P0-026 governance system for centralized authentication, integrates with P0-020 design tokens for consistent theming
- **Problems solved**: Eliminates authentication inconsistencies across UI modules, provides unified navigation experience, enables lazy loading for optimal performance

### What Will Be Implemented
Implement a React shell application that serves as the main container for all LeadFactory UI features, providing:

1. **Unified Navigation**: Global navigation bar with role-based menu items
2. **Authentication Integration**: Centralized authentication using P0-026 governance system
3. **Lazy Loading**: Route-based code splitting for optimal performance
4. **Design System Integration**: Consistent theming using P0-020 design tokens
5. **Security**: Role-based access control with authentication guards
6. **Performance**: Bundle size optimization with lazy loading and preloading

### Success Criteria
- [ ] Global navigation renders with all feature links
- [ ] Authentication integration works with role-based menu items
- [ ] Lazy-loaded routes for each feature function correctly
- [ ] Dark mode support using design tokens
- [ ] Responsive mobile navigation
- [ ] Bundle size stays under 250 kB gzipped per route
- [ ] Authentication guards prevent unauthorized access
- [ ] Coverage ≥ 80% on shell components
- [ ] Visual regression tests pass via Chromatic
- [ ] Accessibility score ≥ 98 (axe-core)

## Context & Background

### Documentation & References
```yaml
- url: https://blog.bitsrc.io/application-shell-for-react-micro-frontends-daa944caa8f3
  why: Application shell patterns for React micro-frontends

- url: https://medium.com/@isuruariyarathna2k00/a-deep-dive-into-micro-frontend-architecture-with-react-js-264ca6edca6b
  why: React micro-frontend architecture implementation guide

- url: https://ui.dev/react-router-protected-routes-authentication
  why: Protected routes and authentication with React Router

- url: https://www.greatfrontend.com/blog/code-splitting-and-lazy-loading-in-react
  why: Code splitting and lazy loading best practices

- url: https://www.design-tokens.dev/guides/tailwind-css/
  why: Design tokens implementation with Tailwind CSS

- url: https://tailwindcss.com/docs/adding-custom-styles
  why: Tailwind CSS custom styles and configuration

- file: /Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final/.claude/research_cache/research_P0-027.txt
  why: Compiled research findings for implementation guidance

- file: /Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final/design/design_tokens.json
  why: Design tokens from P0-020 for consistent theming

- file: /Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final/core/config.py
  why: Authentication configuration patterns

- file: /Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final/api/auth.py
  why: Authentication middleware from P0-026
```

### Current Codebase Tree
```
├── api/
│   ├── auth.py                     # Authentication endpoints
│   ├── governance.py               # Role-based access control
│   └── health.py                   # Health check endpoint
├── core/
│   ├── config.py                   # Configuration management
│   └── auth.py                     # Authentication utilities
├── design/
│   ├── design_tokens.json          # Design tokens from P0-020
│   └── styleguide.html             # Style guide reference
├── static/
│   ├── css/                        # Existing CSS files
│   └── js/                         # Existing JavaScript files
├── templates/
│   └── base.html                   # Base template
└── main.py                         # FastAPI application
```

### Desired Codebase Tree  
```
├── app/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Navigation/
│   │   │   │   ├── Navigation.tsx
│   │   │   │   ├── MobileNav.tsx
│   │   │   │   └── UserMenu.tsx
│   │   │   ├── Layout/
│   │   │   │   ├── AppShell.tsx
│   │   │   │   └── AuthGuard.tsx
│   │   │   └── shared/
│   │   │       ├── Button.tsx
│   │   │       ├── Card.tsx
│   │   │       └── Modal.tsx
│   │   ├── routes/
│   │   │   ├── index.tsx
│   │   │   ├── leads/
│   │   │   │   └── index.lazy.tsx
│   │   │   ├── batch/
│   │   │   │   └── index.lazy.tsx
│   │   │   ├── templates/
│   │   │   │   └── index.lazy.tsx
│   │   │   ├── scoring/
│   │   │   │   └── index.lazy.tsx
│   │   │   ├── lineage/
│   │   │   │   └── index.lazy.tsx
│   │   │   └── governance/
│   │   │       └── index.lazy.tsx
│   │   ├── hooks/
│   │   │   ├── useAuth.ts
│   │   │   └── useNavigation.ts
│   │   ├── utils/
│   │   │   ├── auth.ts
│   │   │   └── routes.ts
│   │   ├── styles/
│   │   │   ├── globals.css
│   │   │   └── tokens.css
│   │   └── App.tsx
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── vite.config.ts
├── static/app/                     # Built React app
└── templates/app.html              # App shell template
```

## Technical Approach

### Integration Points
- **Authentication**: Integrate with existing `/api/auth` endpoints from P0-026
- **Design System**: Use `design/design_tokens.json` for theming
- **Routes**: Mount React app at `/app/*` routes in FastAPI
- **API Integration**: Connect to existing API endpoints for each feature
- **Static Assets**: Serve built React app from `/static/app/`

### Implementation Approach
1. **Setup React Application**:
   - Create React TypeScript app with Vite
   - Configure Tailwind CSS with design tokens
   - Set up React Router 6 with lazy loading
   - Implement authentication context and hooks

2. **Build Shell Components**:
   - Create responsive navigation with role-based menu items
   - Implement authentication guard higher-order component
   - Build reusable UI components using design tokens
   - Set up error boundaries for module loading failures

3. **Configure Routing**:
   - Implement lazy-loaded routes for each feature
   - Set up authentication guards for protected routes
   - Configure code splitting for optimal bundle sizes
   - Add preloading for critical components

4. **Authentication Integration**:
   - Create authentication hook connecting to P0-026 API
   - Implement role-based navigation visibility
   - Add logout functionality with session cleanup
   - Handle token refresh and expiration

5. **Performance Optimization**:
   - Implement route-based code splitting
   - Add bundle size monitoring and limits
   - Configure lazy loading with Suspense
   - Add performance budgets and monitoring

6. **Testing Strategy**:
   - Unit tests for components and hooks
   - Integration tests for authentication flows
   - E2E tests for navigation and routing
   - Visual regression tests via Chromatic

### Error Handling Strategy
- **Module Loading**: Error boundaries for failed lazy loading
- **Authentication**: Graceful handling of auth failures with redirect
- **Network**: Retry logic for API calls with exponential backoff
- **Navigation**: Fallback routes for invalid paths
- **Performance**: Timeout handling for slow-loading modules

## Acceptance Criteria
1. **Navigation Requirements**:
   - Global navigation renders with all feature links
   - Authentication integration works with role-based menu items
   - Responsive mobile navigation functions correctly
   - User menu with logout functionality

2. **Routing Requirements**:
   - Lazy-loaded routes for each feature function correctly
   - Authentication guards prevent unauthorized access
   - Error boundaries handle module loading failures
   - Route transitions complete in < 200ms

3. **Performance Requirements**:
   - Bundle size stays under 250 kB gzipped per route
   - Initial page load < 2 seconds
   - Core Web Vitals: LCP < 2.5s, FID < 100ms, CLS < 0.1
   - Lighthouse accessibility score ≥ 98

4. **Design System Requirements**:
   - Dark mode support using design tokens
   - Consistent theming across all components
   - No hardcoded colors or spacing values
   - WCAG 2.1 AA compliance

5. **Security Requirements**:
   - CSP headers properly configured
   - Server-side session validation
   - CSRF protection for state changes
   - XSS prevention for user inputs

6. **Testing Requirements**:
   - Coverage ≥ 80% on shell components
   - Visual regression tests pass via Chromatic
   - Integration tests for authentication flows
   - E2E tests for critical user journeys

## Dependencies
- **Task Dependencies**: P0-026 (Governance system for authentication)
- **Optional Dependencies**: P0-020 (Design tokens for theming)

### Technical Dependencies
- React 18+ (concurrent features, Suspense improvements)
- React Router 6+ (lazy loading, data loading)
- TypeScript 5+ (type safety, modern features)
- Vite 5+ (build tool, HMR, code splitting)
- Tailwind CSS 3+ (utility-first styling)
- React Query 4+ (API state management)
- Axios 1+ (HTTP client)
- @headlessui/react (accessible components)
- @heroicons/react (icon system)
- React Testing Library (testing utilities)
- Playwright (E2E testing)
- Chromatic (visual regression testing)

## Testing Strategy

### Unit Testing
- **Coverage Target**: ≥ 80% on all shell components
- **Framework**: Jest + React Testing Library
- **Focus Areas**:
  - Component rendering and props
  - Authentication hooks and context
  - Navigation utilities and routing
  - Error boundary functionality

### Integration Testing
- **Authentication Flows**: Login, logout, role-based access
- **Navigation**: Route transitions, lazy loading
- **API Integration**: Connection to P0-026 authentication endpoints
- **Error Handling**: Module loading failures, network errors

### End-to-End Testing
- **Framework**: Playwright
- **Critical User Journeys**:
  - Login and navigate to each feature
  - Role-based menu visibility
  - Logout and session cleanup
  - Mobile navigation functionality

### Visual Regression Testing
- **Tool**: Chromatic + Storybook
- **Components**: Navigation, layout, authentication states
- **Accessibility**: axe-core integration in test suite
- **Performance**: Bundle size monitoring, Lighthouse CI

## Rollback Plan

### Rollback Strategy
- **Feature Flag**: `ENABLE_UNIFIED_SHELL` to revert to individual UI pages
- **Route Fallback**: Maintain existing static HTML pages as fallback
- **Gradual Migration**: Feature flags for each lazy-loaded route
- **Database**: No database changes required for rollback
- **API**: No API changes required for rollback

### Rollback Steps
1. **Immediate Rollback**: Set `ENABLE_UNIFIED_SHELL=false` in environment
2. **Route Restoration**: Restore original static HTML pages
3. **Asset Cleanup**: Remove `/static/app/` directory
4. **Template Restoration**: Restore original template files
5. **Configuration Reset**: Reset FastAPI route configurations

### Rollback Validation
- All original static pages load correctly
- Authentication flows work with original pages
- No broken links or navigation issues
- Performance metrics remain stable

## Validation Framework

### Executable Tests
```bash
# Syntax/Style
cd app && npm run lint && npm run type-check

# Unit Tests  
cd app && npm run test -- --coverage --watchAll=false

# Integration Tests
cd app && npm run test:integration

# E2E Tests
cd app && npm run test:e2e

# Build Test
cd app && npm run build && npm run preview

# Performance Test
cd app && npm run build:analyze
```

### Missing-Checks Validation
**Required for UI/Frontend tasks:**
- [ ] Pre-commit hooks (ESLint, TypeScript, Prettier)
- [ ] Branch protection & required status checks
- [ ] Visual regression & accessibility testing (Chromatic, axe-core)
- [ ] Style-guide enforcement (design token validation)
- [ ] Bundle size monitoring and limits
- [ ] Performance budgets (Lighthouse CI)
- [ ] Accessibility compliance (WCAG 2.1 AA)
- [ ] Security headers (CSP, XSS protection)

**Recommended:**
- [ ] Performance regression budgets
- [ ] Automated CI failure handling
- [ ] Visual diff approval workflow
- [ ] Progressive enhancement testing
- [ ] Cross-browser compatibility testing