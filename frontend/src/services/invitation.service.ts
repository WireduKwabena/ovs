import api from './api';
import type {
  CandidateAccessConsumeResponse,
  CandidateAccessContext,
  CandidateAccessResults,
  Document,
  DocumentType,
  Invitation,
  VettingCase,
} from '@/types';

export interface CandidatePortalDocument {
  id: string;
  case: string;
  document_type: DocumentType;
  document_type_display?: string;
  original_filename?: string;
  file_size?: number;
  status: string;
  processing_error?: string;
  uploaded_at?: string;
  processed_at?: string | null;
  file_url?: string;
}

export const invitationService = {
  async acceptInvitation(token: string): Promise<{
    message: string;
    campaign: string;
    candidate_email: string;
    enrollment_status: string;
    access_url?: string;
  }> {
    const response = await api.post('/invitations/accept/', { token });
    return response.data;
  },

  async consumeAccessToken(token: string, beginVetting = true): Promise<CandidateAccessConsumeResponse> {
    const response = await api.post<CandidateAccessConsumeResponse>('/invitations/access/consume/', {
      token,
      begin_vetting: beginVetting,
    }, { withCredentials: true });
    return response.data;
  },

  async getAccessContext(): Promise<CandidateAccessContext> {
    const response = await api.get<CandidateAccessContext>('/invitations/access/me/', { withCredentials: true });
    return response.data;
  },

  async getAccessResults(): Promise<CandidateAccessResults> {
    const response = await api.get<CandidateAccessResults>('/invitations/access/results/', { withCredentials: true });
    return response.data;
  },

  async logoutAccess(): Promise<{ message: string }> {
    const response = await api.post<{ message: string }>('/invitations/access/logout/', {}, { withCredentials: true });
    return response.data;
  },

  async listCandidateCases(): Promise<VettingCase[]> {
    const response = await api.get<{ results?: VettingCase[] } | VettingCase[]>('/applications/cases/', {
      withCredentials: true,
    });
    if (Array.isArray(response.data)) {
      return response.data;
    }
    return Array.isArray(response.data?.results) ? response.data.results : [];
  },

  async uploadCandidateDocument(caseId: string, file: File, documentType: string): Promise<Document> {
    const formData = new FormData();
    formData.append('document', file);
    formData.append('document_type', documentType);
    const response = await api.post<Document>(
      `/applications/cases/${caseId}/upload-document/`,
      formData,
      {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' },
      },
    );
    return response.data;
  },

  async listCandidateDocuments(caseId: string): Promise<CandidatePortalDocument[]> {
    const response = await api.get<{ results?: CandidatePortalDocument[] } | CandidatePortalDocument[]>(
      '/applications/documents/',
      {
        withCredentials: true,
        params: { case: caseId },
      },
    );
    if (Array.isArray(response.data)) {
      return response.data;
    }
    return Array.isArray(response.data?.results) ? response.data.results : [];
  },

  async sendNow(invitationId: string): Promise<{ message: string }> {
    const response = await api.post<{ message: string }>(`/invitations/${invitationId}/send/`, {});
    return response.data;
  },

  async getById(invitationId: string): Promise<Invitation> {
    const response = await api.get<Invitation>(`/invitations/${invitationId}/`);
    return response.data;
  },
};
