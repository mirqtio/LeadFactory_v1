# LeadFactory Global Navigation Shell

A unified React shell application that hosts all LeadFactory UI features with consistent navigation and authentication, enabling secure, scalable micro-frontend architecture with role-based access control.

## Features

- **Unified Authentication**: Integration with P0-026 authentication system
- **Role-Based Access Control**: Menu items and routes filtered by user permissions
- **Design System Integration**: Uses P0-020 design tokens with Tailwind CSS
- **Dark Mode Support**: System-wide theme switching with persistence
- **Responsive Design**: Mobile-first responsive navigation
- **Lazy Loading**: Route-based code splitting for optimal performance
- **Bundle Size Optimization**: Under 250kB per route as per PRP requirements

## Architecture

### Core Components

- **AppShell**: Main application layout with navigation and authentication
- **Navigation**: Role-based navigation bar with user context
- **AuthGuard**: Route protection based on authentication and roles

### Authentication Integration (P0-026)

The shell integrates with the existing P0-026 authentication system:

- **API Endpoints**: `/account/login`, `/account/me`, `/account/logout`, `/account/refresh`
- **Token Management**: JWT access tokens with automatic refresh
- **Role Detection**: Based on user attributes and RBAC system
- **Persistent Sessions**: Secure token storage with refresh capability

### Design System (P0-020)

- **Design Tokens**: Imported from `../design/design_tokens.json`
- **CSS Custom Properties**: Runtime theme switching support
- **Tailwind Integration**: Design tokens mapped to Tailwind theme
- **Component Patterns**: Consistent styling across all UI components

## Development

### Prerequisites

- Node.js 18+
- TypeScript 5+
- P0-026 authentication system running
- P0-020 design tokens available

### Installation

```bash
cd app
npm install
```

### Development Server

```bash
npm run dev
```

### Build

```bash
npm run build
```

### Testing

```bash
npm run test
```

## Project Structure

```
app/
├── src/
│   ├── components/       # React components
│   │   ├── auth/        # Authentication components
│   │   ├── navigation/  # Navigation components
│   │   └── shell/       # Shell layout components
│   ├── store/           # State management (Zustand)
│   ├── api/             # API client and services
│   ├── types/           # TypeScript type definitions
│   ├── utils/           # Utility functions
│   └── styles/          # CSS and styling
├── public/              # Static assets
├── index.html          # HTML entry point
└── package.json        # Dependencies and scripts
```

## Configuration

### Environment Variables

- `VITE_API_BASE_URL`: Base URL for API calls (defaults to `/api`)
- `VITE_ENABLE_MOCK_AUTH`: Enable mock authentication for development

### Bundle Size Monitoring

The build system warns when bundle sizes exceed 250kB per route:

```typescript
// vite.config.ts
chunkSizeWarningLimit: 250 // 250KB per route as per PRP requirement
```

## Authentication Flow

1. **Login**: User submits credentials via login form
2. **Token Storage**: Access and refresh tokens stored securely
3. **Route Protection**: AuthGuard checks authentication and roles
4. **Automatic Refresh**: Expired tokens refreshed automatically
5. **Navigation Filtering**: Menu items filtered by user role
6. **Logout**: Tokens cleared and user redirected to login

## Role Hierarchy

```
SUPER_ADMIN (7) > ADMIN (6) > MANAGER (5) > TEAM_LEAD (4) > 
ANALYST (3) > SALES_REP (2) / MARKETING_USER (2) > VIEWER (1) > GUEST (0)
```

## Performance

- **Bundle Size**: < 250kB per route
- **Initial Load**: Optimized with lazy loading
- **Code Splitting**: Route-based chunks
- **Caching**: Intelligent token and theme caching
- **Responsive**: Mobile-first design with touch support

## Security

- **JWT Tokens**: Secure token-based authentication
- **HTTPS Only**: All API calls over secure connections
- **Role Validation**: Server-side permission checks
- **Token Refresh**: Automatic renewal of expired tokens
- **Secure Storage**: No sensitive data in localStorage