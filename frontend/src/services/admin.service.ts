// src/services/admin.service.ts
import api from './api';
import type {
  AdminCasesResponse,
  AdminManagedUser,
  AdminUsersResponse,
  AdminUserUpdatePayload,
  ApiError,
  DashboardStats,
} from '@/types';

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

  async updateCaseStatus(caseIdentifier: string, status: 'approved' | 'rejected' | 'under_review'): Promise<void> {
    try {
      await api.patch(`/applications/cases/${caseIdentifier}/`, { status });
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Case status update failed');
    }
  },

  async getUsers(params?: {
    q?: string;
    user_type?: 'admin' | 'hr_manager' | 'applicant';
    is_active?: boolean;
    page?: number;
    page_size?: number;
    ordering?: string;
  }): Promise<AdminUsersResponse> {
    try {
      const response = await api.get<AdminUsersResponse>('/admin/users/', { params });
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Users fetch failed');
    }
  },

  async updateUser(userId: string, payload: AdminUserUpdatePayload): Promise<AdminManagedUser> {
    try {
      const response = await api.patch<AdminManagedUser>(`/admin/users/${userId}/`, payload);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'User update failed');
    }
  },
};
