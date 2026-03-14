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

type AdminCaseQuery = {
  status?: string;
  application_type?: string;
  priority?: string;
  page?: number;
  page_size?: number;
  ordering?: string;
};

type AdminUserQuery = {
  q?: string;
  user_type?: 'admin' | 'internal' | 'applicant';
  is_active?: boolean;
  page?: number;
  page_size?: number;
  ordering?: string;
};

const withOrganizationHeader = (organizationId?: string) => {
  const normalizedOrganizationId = String(organizationId || '').trim();
  if (!normalizedOrganizationId) {
    return {};
  }

  return {
    headers: {
      'X-Active-Organization-ID': normalizedOrganizationId,
    },
  };
};

const getDashboard = async (): Promise<DashboardStats> => {
  try {
    const response = await api.get<DashboardStats>('/admin/dashboard/');
    return response.data;
  } catch (error: any) {
    throw new Error((error.response?.data as ApiError)?.message || 'Dashboard fetch failed');
  }
};

const getAnalytics = async (params?: { months?: number }): Promise<any> => {
  try {
    const response = await api.get('/admin/analytics/', { params });
    return response.data;
  } catch (error: any) {
    throw new Error((error.response?.data as ApiError)?.message || 'Analytics fetch failed');
  }
};

const getInterviewAnalytics = async (params?: { days?: number }): Promise<any> => {
  try {
    const response = await api.get('/interviews/sessions/analytics-dashboard/', { params });
    return response.data;
  } catch (error: any) {
    throw new Error((error.response?.data as ApiError)?.message || 'Interview analytics fetch failed');
  }
};

const getCases = async (params?: AdminCaseQuery): Promise<AdminCasesResponse> => {
  try {
    const response = await api.get<AdminCasesResponse>('/admin/cases/', { params });
    return response.data;
  } catch (error: any) {
    throw new Error((error.response?.data as ApiError)?.message || 'Cases fetch failed');
  }
};

const getOrgCases = async (
  organizationId: string,
  params?: AdminCaseQuery,
): Promise<AdminCasesResponse> => {
  try {
    const response = await api.get<AdminCasesResponse>('/admin/cases/', {
      params,
      ...withOrganizationHeader(organizationId),
    });
    return response.data;
  } catch (error: any) {
    throw new Error((error.response?.data as ApiError)?.message || 'Organization cases fetch failed');
  }
};

const updateCaseStatus = async (
  caseIdentifier: string,
  status: 'approved' | 'rejected' | 'under_review',
): Promise<void> => {
  try {
    await api.patch(`/applications/cases/${caseIdentifier}/`, { status });
  } catch (error: any) {
    throw new Error((error.response?.data as ApiError)?.message || 'Case status update failed');
  }
};

const updateOrgCaseStatus = async (
  organizationId: string,
  caseIdentifier: string,
  status: 'approved' | 'rejected' | 'under_review',
): Promise<void> => {
  try {
    await api.patch(
      `/applications/cases/${caseIdentifier}/`,
      { status },
      withOrganizationHeader(organizationId),
    );
  } catch (error: any) {
    throw new Error((error.response?.data as ApiError)?.message || 'Organization case status update failed');
  }
};

const getUsers = async (params?: AdminUserQuery): Promise<AdminUsersResponse> => {
  try {
    const response = await api.get<AdminUsersResponse>('/admin/users/', { params });
    return response.data;
  } catch (error: any) {
    throw new Error((error.response?.data as ApiError)?.message || 'Users fetch failed');
  }
};

const getOrgUsers = async (
  organizationId: string,
  params?: AdminUserQuery,
): Promise<AdminUsersResponse> => {
  try {
    const response = await api.get<AdminUsersResponse>('/admin/users/', {
      params,
      ...withOrganizationHeader(organizationId),
    });
    return response.data;
  } catch (error: any) {
    throw new Error((error.response?.data as ApiError)?.message || 'Organization users fetch failed');
  }
};

const updateUser = async (
  userId: string,
  payload: AdminUserUpdatePayload,
): Promise<AdminManagedUser> => {
  try {
    const response = await api.patch<AdminManagedUser>(`/admin/users/${userId}/`, payload);
    return response.data;
  } catch (error: any) {
    throw new Error((error.response?.data as ApiError)?.message || 'User update failed');
  }
};

const updateOrgUser = async (
  organizationId: string,
  userId: string,
  payload: AdminUserUpdatePayload,
): Promise<AdminManagedUser> => {
  try {
    const response = await api.patch<AdminManagedUser>(
      `/admin/users/${userId}/`,
      payload,
      withOrganizationHeader(organizationId),
    );
    return response.data;
  } catch (error: any) {
    throw new Error((error.response?.data as ApiError)?.message || 'Organization user update failed');
  }
};

export const adminService = {
  getDashboard,
  getAnalytics,
  getInterviewAnalytics,
  getCases,
  getOrgCases,
  updateCaseStatus,
  updateOrgCaseStatus,
  getUsers,
  getOrgUsers,
  updateUser,
  updateOrgUser,
  platform: {
    getDashboard,
    getAnalytics,
    getInterviewAnalytics,
    getCases,
    getUsers,
    updateUser,
    updateCaseStatus,
  },
  org: {
    getCases: getOrgCases,
    getUsers: getOrgUsers,
    updateUser: updateOrgUser,
    updateCaseStatus: updateOrgCaseStatus,
  },
};

