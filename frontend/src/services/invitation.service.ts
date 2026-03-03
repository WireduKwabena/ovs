import api from './api';
import type {
  CandidateAccessConsumeResponse,
  CandidateAccessContext,
  CandidateAccessResults,
  Invitation,
} from '@/types';

export const invitationService = {
  async acceptInvitation(token: string): Promise<{
    message: string;
    campaign: string;
    candidate_email: string;
    enrollment_status: string;
  }> {
    const response = await api.post('/invitations/accept/', { token });
    return response.data;
  },

  async consumeAccessToken(token: string, beginVetting = true): Promise<CandidateAccessConsumeResponse> {
    const response = await api.post<CandidateAccessConsumeResponse>('/invitations/access/consume/', {
      token,
      begin_vetting: beginVetting,
    });
    return response.data;
  },

  async getAccessContext(): Promise<CandidateAccessContext> {
    const response = await api.get<CandidateAccessContext>('/invitations/access/me/');
    return response.data;
  },

  async getAccessResults(): Promise<CandidateAccessResults> {
    const response = await api.get<CandidateAccessResults>('/invitations/access/results/');
    return response.data;
  },

  async logoutAccess(): Promise<{ message: string }> {
    const response = await api.post<{ message: string }>('/invitations/access/logout/', {});
    return response.data;
  },

  async sendNow(invitationId: number | string): Promise<{ message: string }> {
    const response = await api.post<{ message: string }>(`/invitations/${invitationId}/send/`, {});
    return response.data;
  },

  async getById(invitationId: number | string): Promise<Invitation> {
    const response = await api.get<Invitation>(`/invitations/${invitationId}/`);
    return response.data;
  },
};
