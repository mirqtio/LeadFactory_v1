/**
 * Zustand store for P2-020 Personalization MVP
 * Global state management for user preferences, saved searches, and dashboard layout
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type {
  User,
  UserPreferences,
  SavedSearch,
  PersonalizationTemplate,
  PersonalizationMetrics,
  DashboardLayout,
  DashboardWidget,
  SearchFilters
} from '@types/index';

interface PersonalizationState {
  // User state
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  error: string | null;

  // Preferences
  preferences: UserPreferences | null;
  preferencesLoading: boolean;

  // Saved searches
  savedSearches: SavedSearch[];
  savedSearchesLoading: boolean;
  currentSearch: SavedSearch | null;

  // Personalization
  templates: PersonalizationTemplate[];
  templatesLoading: boolean;
  metrics: PersonalizationMetrics | null;
  metricsLoading: boolean;

  // Dashboard
  dashboardLayout: DashboardLayout | null;
  customizingLayout: boolean;
  availableWidgets: DashboardWidget[];

  // UI state
  sidebarOpen: boolean;
  searchPanelOpen: boolean;
  preferencesModalOpen: boolean;
  layoutCustomizerOpen: boolean;

  // Actions
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;

  // Preferences actions
  setPreferences: (preferences: UserPreferences) => void;
  updatePreferences: (updates: Partial<UserPreferences>) => void;
  setPreferencesLoading: (loading: boolean) => void;

  // Saved searches actions
  setSavedSearches: (searches: SavedSearch[]) => void;
  addSavedSearch: (search: SavedSearch) => void;
  updateSavedSearch: (searchId: string, updates: Partial<SavedSearch>) => void;
  deleteSavedSearch: (searchId: string) => void;
  setCurrentSearch: (search: SavedSearch | null) => void;
  setSavedSearchesLoading: (loading: boolean) => void;

  // Personalization actions
  setTemplates: (templates: PersonalizationTemplate[]) => void;
  setTemplatesLoading: (loading: boolean) => void;
  setMetrics: (metrics: PersonalizationMetrics) => void;
  setMetricsLoading: (loading: boolean) => void;

  // Dashboard actions
  setDashboardLayout: (layout: DashboardLayout) => void;
  updateDashboardLayout: (updates: Partial<DashboardLayout>) => void;
  addWidget: (widget: DashboardWidget) => void;
  removeWidget: (widgetId: string) => void;
  updateWidget: (widgetId: string, updates: Partial<DashboardWidget>) => void;
  reorderWidgets: (widgets: DashboardWidget[]) => void;
  setCustomizingLayout: (customizing: boolean) => void;
  setAvailableWidgets: (widgets: DashboardWidget[]) => void;

  // UI actions
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  toggleSearchPanel: () => void;
  setSearchPanelOpen: (open: boolean) => void;
  togglePreferencesModal: () => void;
  setPreferencesModalOpen: (open: boolean) => void;
  toggleLayoutCustomizer: () => void;
  setLayoutCustomizerOpen: (open: boolean) => void;

  // Utility actions
  reset: () => void;
}

const initialState = {
  user: null,
  isAuthenticated: false,
  loading: false,
  error: null,
  preferences: null,
  preferencesLoading: false,
  savedSearches: [],
  savedSearchesLoading: false,
  currentSearch: null,
  templates: [],
  templatesLoading: false,
  metrics: null,
  metricsLoading: false,
  dashboardLayout: null,
  customizingLayout: false,
  availableWidgets: [],
  sidebarOpen: true,
  searchPanelOpen: false,
  preferencesModalOpen: false,
  layoutCustomizerOpen: false,
};

export const usePersonalizationStore = create<PersonalizationState>()(
  persist(
    (set, get) => ({
      ...initialState,

      // Basic setters
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setLoading: (loading) => set({ loading }),
      setError: (error) => set({ error }),

      // Preferences
      setPreferences: (preferences) => set({ preferences }),
      updatePreferences: (updates) => {
        const current = get().preferences;
        if (current) {
          set({ preferences: { ...current, ...updates } });
        }
      },
      setPreferencesLoading: (preferencesLoading) => set({ preferencesLoading }),

      // Saved searches
      setSavedSearches: (savedSearches) => set({ savedSearches }),
      addSavedSearch: (search) => {
        const current = get().savedSearches;
        set({ savedSearches: [search, ...current] });
      },
      updateSavedSearch: (searchId, updates) => {
        const current = get().savedSearches;
        const updated = current.map(search =>
          search.id === searchId ? { ...search, ...updates } : search
        );
        set({ savedSearches: updated });
      },
      deleteSavedSearch: (searchId) => {
        const current = get().savedSearches;
        const filtered = current.filter(search => search.id !== searchId);
        set({ savedSearches: filtered });
      },
      setCurrentSearch: (currentSearch) => set({ currentSearch }),
      setSavedSearchesLoading: (savedSearchesLoading) => set({ savedSearchesLoading }),

      // Personalization
      setTemplates: (templates) => set({ templates }),
      setTemplatesLoading: (templatesLoading) => set({ templatesLoading }),
      setMetrics: (metrics) => set({ metrics }),
      setMetricsLoading: (metricsLoading) => set({ metricsLoading }),

      // Dashboard layout
      setDashboardLayout: (dashboardLayout) => set({ dashboardLayout }),
      updateDashboardLayout: (updates) => {
        const current = get().dashboardLayout;
        if (current) {
          set({ dashboardLayout: { ...current, ...updates } });
        }
      },
      addWidget: (widget) => {
        const current = get().dashboardLayout;
        if (current) {
          const updatedWidgets = [...current.widgets, widget];
          set({
            dashboardLayout: { ...current, widgets: updatedWidgets }
          });
        }
      },
      removeWidget: (widgetId) => {
        const current = get().dashboardLayout;
        if (current) {
          const filteredWidgets = current.widgets.filter(w => w.id !== widgetId);
          set({
            dashboardLayout: { ...current, widgets: filteredWidgets }
          });
        }
      },
      updateWidget: (widgetId, updates) => {
        const current = get().dashboardLayout;
        if (current) {
          const updatedWidgets = current.widgets.map(widget =>
            widget.id === widgetId ? { ...widget, ...updates } : widget
          );
          set({
            dashboardLayout: { ...current, widgets: updatedWidgets }
          });
        }
      },
      reorderWidgets: (widgets) => {
        const current = get().dashboardLayout;
        if (current) {
          set({
            dashboardLayout: { ...current, widgets }
          });
        }
      },
      setCustomizingLayout: (customizingLayout) => set({ customizingLayout }),
      setAvailableWidgets: (availableWidgets) => set({ availableWidgets }),

      // UI state
      toggleSidebar: () => set(state => ({ sidebarOpen: !state.sidebarOpen })),
      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
      toggleSearchPanel: () => set(state => ({ searchPanelOpen: !state.searchPanelOpen })),
      setSearchPanelOpen: (searchPanelOpen) => set({ searchPanelOpen }),
      togglePreferencesModal: () => set(state => ({ preferencesModalOpen: !state.preferencesModalOpen })),
      setPreferencesModalOpen: (preferencesModalOpen) => set({ preferencesModalOpen }),
      toggleLayoutCustomizer: () => set(state => ({ layoutCustomizerOpen: !state.layoutCustomizerOpen })),
      setLayoutCustomizerOpen: (layoutCustomizerOpen) => set({ layoutCustomizerOpen }),

      // Reset
      reset: () => set(initialState),
    }),
    {
      name: 'personalization-store',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        // Only persist UI preferences and some user data
        user: state.user,
        isAuthenticated: state.isAuthenticated,
        preferences: state.preferences,
        sidebarOpen: state.sidebarOpen,
        dashboardLayout: state.dashboardLayout,
      }),
    }
  )
);

// Computed selectors
export const useAuth = () => {
  const { user, isAuthenticated, loading } = usePersonalizationStore();
  return { user, isAuthenticated, loading };
};

export const usePreferences = () => {
  const {
    preferences,
    preferencesLoading,
    setPreferences,
    updatePreferences,
    setPreferencesLoading
  } = usePersonalizationStore();
  return {
    preferences,
    loading: preferencesLoading,
    setPreferences,
    updatePreferences,
    setLoading: setPreferencesLoading
  };
};

export const useSavedSearches = () => {
  const {
    savedSearches,
    savedSearchesLoading,
    currentSearch,
    setSavedSearches,
    addSavedSearch,
    updateSavedSearch,
    deleteSavedSearch,
    setCurrentSearch,
    setSavedSearchesLoading
  } = usePersonalizationStore();
  return {
    searches: savedSearches,
    loading: savedSearchesLoading,
    currentSearch,
    setSearches: setSavedSearches,
    addSearch: addSavedSearch,
    updateSearch: updateSavedSearch,
    deleteSearch: deleteSavedSearch,
    setCurrentSearch,
    setLoading: setSavedSearchesLoading
  };
};

export const useDashboardLayout = () => {
  const {
    dashboardLayout,
    customizingLayout,
    availableWidgets,
    setDashboardLayout,
    updateDashboardLayout,
    addWidget,
    removeWidget,
    updateWidget,
    reorderWidgets,
    setCustomizingLayout,
    setAvailableWidgets
  } = usePersonalizationStore();
  return {
    layout: dashboardLayout,
    customizing: customizingLayout,
    availableWidgets,
    setLayout: setDashboardLayout,
    updateLayout: updateDashboardLayout,
    addWidget,
    removeWidget,
    updateWidget,
    reorderWidgets,
    setCustomizing: setCustomizingLayout,
    setAvailableWidgets
  };
};

export const useUI = () => {
  const {
    sidebarOpen,
    searchPanelOpen,
    preferencesModalOpen,
    layoutCustomizerOpen,
    toggleSidebar,
    setSidebarOpen,
    toggleSearchPanel,
    setSearchPanelOpen,
    togglePreferencesModal,
    setPreferencesModalOpen,
    toggleLayoutCustomizer,
    setLayoutCustomizerOpen
  } = usePersonalizationStore();
  return {
    sidebarOpen,
    searchPanelOpen,
    preferencesModalOpen,
    layoutCustomizerOpen,
    toggleSidebar,
    setSidebarOpen,
    toggleSearchPanel,
    setSearchPanelOpen,
    togglePreferencesModal,
    setPreferencesModalOpen,
    toggleLayoutCustomizer,
    setLayoutCustomizerOpen
  };
};