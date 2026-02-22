// src/services/admin.service.ts (Tweaked)
import api from './api';
import type { DashboardStats, PaginatedResponse, VettingCase, ApiError } from '@/types';

export const adminService = {
  async getDashboard(): Promise<DashboardStats> {
    try {
      const response = await api.get<DashboardStats>('/admin/dashboard/');
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Dashboard fetch failed');
    }
  },

  async getAnalytics(): Promise<any> {  // Type if known (e.g., AnalyticsData)
    try {
      const response = await api.get('/admin/analytics/');
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Analytics fetch failed');
    }
  },

  async getCases(params?: {
    status?: string;
    application_type?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<VettingCase>> {  // Typed pagination
    try {
      const response = await api.get<PaginatedResponse<VettingCase>>('/admin/cases/', { params });
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Cases fetch failed');
    }
  },
};