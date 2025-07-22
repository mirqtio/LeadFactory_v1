/**
 * Core component exports for Global Navigation Shell
 */

// Authentication components
export { default as AuthGuard } from './auth/AuthGuard'

// Navigation components  
export { default as Navigation } from './navigation/Navigation'

// Shell components
export { 
  default as AppShell,
  PublicShell,
  AuthenticatedShell,
  AdminShell,
  FullScreenShell
} from './shell/AppShell'