/**
 * TypeScript interfaces for P2-020 Personalization MVP
 * User preferences dashboard with saved searches and customizable layout
 */

export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  role: 'admin' | 'user' | 'viewer';
  preferences: UserPreferences;
}

export interface UserPreferences {
  id: string;
  userId: string;
  theme: 'light' | 'dark' | 'auto';
  language: 'en' | 'es' | 'fr' | 'de';
  timezone: string;
  notifications: NotificationSettings;
  dashboard: DashboardLayout;
  emailSettings: EmailPreferences;
  createdAt: string;
  updatedAt: string;
}

export interface NotificationSettings {
  email: boolean;
  browser: boolean;
  leadUpdates: boolean;
  systemAlerts: boolean;
  weeklyReports: boolean;
  marketingEmails: boolean;
}

export interface DashboardLayout {
  widgets: DashboardWidget[];
  layout: 'grid' | 'list' | 'kanban';
  density: 'compact' | 'comfortable' | 'spacious';
  refreshInterval: number; // minutes
}

export interface DashboardWidget {
  id: string;
  type: 'search' | 'metrics' | 'recent-leads' | 'saved-searches' | 'performance' | 'quick-actions';
  position: { x: number; y: number; w: number; h: number };
  visible: boolean;
  config: Record<string, any>;
}

export interface EmailPreferences {
  templates: string[];
  personalizationLevel: 'low' | 'medium' | 'high';
  autoPersonalization: boolean;
  subjectLineVariants: number;
  bodyVariants: number;
  spamScoreThreshold: number;
}

export interface SavedSearch {
  id: string;
  userId: string;
  name: string;
  description?: string;
  filters: SearchFilters;
  sortBy: string;
  isPublic: boolean;
  tags: string[];
  lastUsed: string;
  useCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface SearchFilters {
  query?: string;
  industry?: string[];
  companySize?: string[];
  location?: string[];
  scoreRange?: { min: number; max: number };
  revenue?: string[];
  leadSource?: string[];
  status?: string[];
  tags?: string[];
  dateRange?: { start: string; end: string };
}

export interface PersonalizationTemplate {
  id: string;
  name: string;
  description: string;
  type: 'email' | 'subject' | 'content';
  template: string;
  variables: string[];
  industry?: string;
  companySize?: string;
  isActive: boolean;
  usageCount: number;
  performanceScore: number;
  createdAt: string;
  updatedAt: string;
}

export interface PersonalizationMetrics {
  totalEmails: number;
  personalizedEmails: number;
  personalizationRate: number;
  averageSpamScore: number;
  openRate: number;
  clickRate: number;
  responseRate: number;
  averagePersonalizationScore: number;
}

export interface QuickAction {
  id: string;
  name: string;
  description: string;
  icon: string;
  action: string;
  params?: Record<string, any>;
  requiresConfirmation: boolean;
  enabled: boolean;
}

// API Response types
export interface ApiResponse<T> {
  data: T;
  message?: string;
  status: 'success' | 'error';
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

// Component prop types
export interface DashboardProps {
  user: User;
  preferences: UserPreferences;
  onPreferencesChange: (preferences: UserPreferences) => void;
}

export interface SavedSearchCardProps {
  search: SavedSearch;
  onUse: (search: SavedSearch) => void;
  onEdit: (search: SavedSearch) => void;
  onDelete: (searchId: string) => void;
  onShare: (search: SavedSearch) => void;
}

export interface PreferencesFormProps {
  preferences: UserPreferences;
  onSave: (preferences: UserPreferences) => void;
  onCancel: () => void;
  loading?: boolean;
}

export interface LayoutCustomizerProps {
  layout: DashboardLayout;
  onLayoutChange: (layout: DashboardLayout) => void;
  availableWidgets: DashboardWidget[];
}

// Form types
export interface SearchForm {
  name: string;
  description: string;
  filters: SearchFilters;
  isPublic: boolean;
  tags: string[];
}

export interface PersonalizationForm {
  name: string;
  description: string;
  type: 'email' | 'subject' | 'content';
  template: string;
  variables: string[];
  industry?: string;
  companySize?: string;
}

// Error types
export interface ValidationError {
  field: string;
  message: string;
}

export interface ApiError {
  message: string;
  code?: string;
  details?: ValidationError[];
}