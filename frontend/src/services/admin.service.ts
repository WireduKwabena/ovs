// src/services/admin.service.ts
import api from './api';
import type { AdminCasesResponse, ApiError, DashboardStats } from '@/types';

export const adminService = {
  async getDashboard(): Promise<DashboardStats> {
    try {
      const response = await api.get<DashboardStats>('/admin/dashboard/');
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Dashboard fetch failed');
    }
  },

  async getAnalytics(params?: { months?: number }): Promise<any> {
    try {
      const response = await api.get('/admin/analytics/', { params });
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Analytics fetch failed');
    }
  },

  async getInterviewAnalytics(params?: { days?: number }): Promise<any> {
    try {
      const response = await api.get('/interviews/sessions/analytics-dashboard/', { params });
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Interview analytics fetch failed');
    }
  },

  async getCases(params?: {
    status?: string;
    application_type?: string;
    priority?: string;
    page?: number;
    page_size?: number;
    ordering?: string;
  }): Promise<AdminCasesResponse> {
    try {
      const response = await api.get<AdminCasesResponse>('/admin/cases/', { params });
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Cases fetch failed');
    }
  },

  async updateCaseStatus(casePk: number, status: 'approved' | 'rejected' | 'under_review'): Promise<void> {
    try {
      await api.patch(`/applications/cases/${casePk}/`, { status });
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Case status update failed');
    }
  },
};
