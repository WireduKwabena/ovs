// src/services/application.service.ts (Tweaked)
import api from './api';
import type {
  VettingCase,
  ApplicationWithDocuments,
  VerificationStatusType,
  Document,
  ApiError,
} from '@/types';

export interface CreateApplicationData {
  application_type: string;
  priority: string;
  notes?: string;
}

// ✅ Add paginated response type
interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export const applicationService = {
  async create(data: CreateApplicationData): Promise<VettingCase> {
    try {
      const response = await api.post<VettingCase>('/applications/', data);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Creation failed');
    }
  },

  async getAll(): Promise<ApplicationWithDocuments[]> {
    try {
      const response = await api.get<PaginatedResponse<ApplicationWithDocuments>>('/applications/');
      console.log('API response for applications:', response.data);

      // ✅ Extract results array from paginated response
      if (response.data && typeof response.data === 'object' && 'results' in response.data) {
        const applications = response.data.results;
        console.log('✅ Extracted applications array:', applications);
        return Array.isArray(applications) ? applications : [];
      }

      // Fallback for non-paginated
      if (Array.isArray(response.data)) {
        return response.data;
      }
      
      console.error('Unexpected API response structure:', response.data);
      return [];
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Fetch failed');
    }
  },

  async getById(caseId: string): Promise<ApplicationWithDocuments> {
    try {
      const response = await api.get<ApplicationWithDocuments>(`/applications/${caseId}/`);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Detail fetch failed');
    }
  },

  async update(caseId: string, data: Partial<VettingCase>): Promise<VettingCase> {
    try {
      const response = await api.patch<VettingCase>(`/applications/${caseId}/`, data);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Update failed');
    }
  },

  async delete(caseId: string): Promise<void> {
    try {
      await api.delete(`/applications/${caseId}/`);
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Deletion failed');
    }
  },

  async approve(caseId: string): Promise<VettingCase> {  // Implemented
    return applicationService.update(caseId, { status: 'approved' });
  },

  async reject(caseId: string): Promise<VettingCase> {  // Implemented
    return applicationService.update(caseId, { status: 'rejected' });
  },

  async uploadDocument(
    caseId: string,
    file: File,
    documentType: string
  ): Promise<{ document: Document; message?: string }> {  // Typed response
    try {
      const formData = new FormData();
      formData.append('document', file);
      formData.append('document_type', documentType);

      const response = await api.post(
        `/applications/${caseId}/upload_document/`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Upload failed');
    }
  },

  async getVerificationStatus(caseId: string): Promise<VerificationStatusType> {
    try {
      const response = await api.get<VerificationStatusType>(
        `/applications/${caseId}/verification_status/`
      );
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Status fetch failed');
    }
  },
};