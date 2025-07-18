/**
 * API client for P2-020 Personalization MVP
 * Integrates with existing d8_personalization FastAPI backend
 */

import axios, { AxiosInstance, AxiosResponse } from 'axios';
import type {
  User,
  UserPreferences,
  SavedSearch,
  PersonalizationTemplate,
  PersonalizationMetrics,
  ApiResponse,
  PaginatedResponse,
  SearchFilters
} from '@types/index';

class ApiClient {
  private client: AxiosInstance;

  constructor(baseURL: string = '/api/v1') {
    this.client = axios.create({
      baseURL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor for auth
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('authToken');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          // Handle unauthorized - redirect to login
          localStorage.removeItem('authToken');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // User preferences
  async getUserPreferences(userId: string): Promise<UserPreferences> {
    const response = await this.client.get<ApiResponse<UserPreferences>>(
      `/users/${userId}/preferences`
    );
    return response.data.data;
  }

  async updateUserPreferences(
    userId: string,
    preferences: Partial<UserPreferences>
  ): Promise<UserPreferences> {
    const response = await this.client.put<ApiResponse<UserPreferences>>(
      `/users/${userId}/preferences`,
      preferences
    );
    return response.data.data;
  }

  // Saved searches
  async getSavedSearches(
    userId: string,
    page: number = 1,
    limit: number = 20
  ): Promise<PaginatedResponse<SavedSearch>> {
    const response = await this.client.get<PaginatedResponse<SavedSearch>>(
      `/users/${userId}/saved-searches`,
      {
        params: { page, limit }
      }
    );
    return response.data;
  }

  async createSavedSearch(savedSearch: Omit<SavedSearch, 'id' | 'createdAt' | 'updatedAt'>): Promise<SavedSearch> {
    const response = await this.client.post<ApiResponse<SavedSearch>>(
      '/saved-searches',
      savedSearch
    );
    return response.data.data;
  }

  async updateSavedSearch(
    searchId: string,
    updates: Partial<SavedSearch>
  ): Promise<SavedSearch> {
    const response = await this.client.put<ApiResponse<SavedSearch>>(
      `/saved-searches/${searchId}`,
      updates
    );
    return response.data.data;
  }

  async deleteSavedSearch(searchId: string): Promise<void> {
    await this.client.delete(`/saved-searches/${searchId}`);
  }

  async useSavedSearch(searchId: string): Promise<void> {
    await this.client.post(`/saved-searches/${searchId}/use`);
  }

  // Personalization templates - integrating with existing d8_personalization API
  async getPersonalizationTemplates(): Promise<PersonalizationTemplate[]> {
    const response = await this.client.get<ApiResponse<PersonalizationTemplate[]>>(
      '/personalization/templates'
    );
    return response.data.data;
  }

  async generatePersonalizedContent(
    leadId: string,
    template: string,
    context: Record<string, any>
  ): Promise<any> {
    const response = await this.client.post<ApiResponse<any>>(
      '/personalization/generate',
      {
        lead_id: leadId,
        template,
        context
      }
    );
    return response.data.data;
  }

  async checkSpamScore(subject: string, body: string): Promise<any> {
    const response = await this.client.post<ApiResponse<any>>(
      '/personalization/spam-check',
      {
        subject,
        body
      }
    );
    return response.data.data;
  }

  async generateSubjectLines(
    industry?: string,
    context?: Record<string, any>,
    tone: string = 'professional',
    count: number = 5
  ): Promise<any> {
    const response = await this.client.post<ApiResponse<any>>(
      '/personalization/subject-lines',
      {
        industry,
        context,
        tone,
        count
      }
    );
    return response.data.data;
  }

  // Personalization metrics
  async getPersonalizationMetrics(
    userId: string,
    dateRange?: { start: string; end: string }
  ): Promise<PersonalizationMetrics> {
    const response = await this.client.get<ApiResponse<PersonalizationMetrics>>(
      `/users/${userId}/personalization-metrics`,
      {
        params: dateRange
      }
    );
    return response.data.data;
  }

  // Search functionality
  async searchLeads(filters: SearchFilters, page: number = 1, limit: number = 20): Promise<any> {
    const response = await this.client.post<any>(
      '/leads/search',
      {
        filters,
        page,
        limit
      }
    );
    return response.data;
  }

  // Dashboard widgets data
  async getDashboardData(userId: string, widgets: string[]): Promise<Record<string, any>> {
    const response = await this.client.get<ApiResponse<Record<string, any>>>(
      `/users/${userId}/dashboard`,
      {
        params: { widgets: widgets.join(',') }
      }
    );
    return response.data.data;
  }

  // User management
  async getCurrentUser(): Promise<User> {
    const response = await this.client.get<ApiResponse<User>>('/auth/me');
    return response.data.data;
  }

  async updateUser(userId: string, updates: Partial<User>): Promise<User> {
    const response = await this.client.put<ApiResponse<User>>(
      `/users/${userId}`,
      updates
    );
    return response.data.data;
  }

  // Export functionality
  async exportSavedSearches(userId: string, format: 'json' | 'csv' = 'json'): Promise<Blob> {
    const response = await this.client.get(
      `/users/${userId}/saved-searches/export`,
      {
        params: { format },
        responseType: 'blob'
      }
    );
    return response.data;
  }

  async exportPersonalizationData(
    userId: string,
    dateRange?: { start: string; end: string },
    format: 'json' | 'csv' = 'json'
  ): Promise<Blob> {
    const response = await this.client.get(
      `/users/${userId}/personalization/export`,
      {
        params: { ...dateRange, format },
        responseType: 'blob'
      }
    );
    return response.data;
  }
}

// Create and export singleton instance
const apiClient = new ApiClient();
export default apiClient;