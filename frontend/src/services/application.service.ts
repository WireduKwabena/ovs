// src/services/application.service.ts (Tweaked)
import api from './api';
import type {
  VettingCase,
  ApplicationWithDocuments,
  VerificationStatusResponse,
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
      const response = await api.post<VettingCase>('/applications/cases/', data);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Creation failed');
    }
  },

  async getAll(options?: { scope?: 'all' | 'assigned' | 'mine' }): Promise<ApplicationWithDocuments[]> {
    try {
      const response = await api.get<PaginatedResponse<ApplicationWithDocuments>>('/applications/cases/', {
        params: options?.scope ? { scope: options.scope } : undefined,
      });
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
      const response = await api.get<ApplicationWithDocuments>(`/applications/cases/${caseId}/`);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Detail fetch failed');
    }
  },

  async update(caseId: string, data: Partial<VettingCase>): Promise<VettingCase> {
    try {
      const response = await api.patch<VettingCase>(`/applications/cases/${caseId}/`, data);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Update failed');
    }
  },

  async delete(caseId: string): Promise<void> {
    try {
      await api.delete(`/applications/cases/${caseId}/`);
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
        `/applications/cases/${caseId}/upload-document/`,
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

  async getVerificationStatus(caseId: string): Promise<VerificationStatusResponse> {
    try {
      const response = await api.get<VerificationStatusResponse>(
        `/applications/cases/${caseId}/verification-status/`
      );
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Status fetch failed');
    }
  },

  async recheckSocialProfiles(caseId: string): Promise<ApplicationWithDocuments> {
    try {
      const response = await api.post<ApplicationWithDocuments>(
        `/applications/cases/${caseId}/recheck-social-profiles/`,
        {},
      );
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Social profile recheck failed');
    }
  },

  async listDocuments(): Promise<Document[]> {
    try {
      const response = await api.get<PaginatedResponse<Document> | Document[]>('/applications/documents/');
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return Array.isArray(response.data.results) ? response.data.results : [];
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Document list fetch failed');
    }
  },

  async getDocumentById(documentId: string): Promise<Document> {
    try {
      const response = await api.get<Document>(`/applications/documents/${documentId}/`);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Document detail fetch failed');
    }
  },
};
