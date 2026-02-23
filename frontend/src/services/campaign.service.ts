import api from './api';
import type {
  CandidateEnrollment,
  CandidateImportResult,
  CandidateImportRow,
  CampaignDashboard,
  PaginatedResponse,
  VettingCampaign,
  Invitation,
} from '@/types';

export interface CreateCampaignData {
  name: string;
  description?: string;
  status?: 'draft' | 'active' | 'closed' | 'archived';
  starts_at?: string | null;
  ends_at?: string | null;
  settings_json?: Record<string, unknown>;
}

function extractResults<T>(payload: PaginatedResponse<T> | T[]): T[] {
  if (Array.isArray(payload)) {
    return payload;
  }
  return Array.isArray(payload.results) ? payload.results : [];
}

export const campaignService = {
  async list(): Promise<VettingCampaign[]> {
    const response = await api.get<PaginatedResponse<VettingCampaign> | VettingCampaign[]>('/campaigns/');
    return extractResults(response.data);
  },

  async getById(campaignId: number | string): Promise<VettingCampaign> {
    const response = await api.get<VettingCampaign>(`/campaigns/${campaignId}/`);
    return response.data;
  },

  async create(payload: CreateCampaignData): Promise<VettingCampaign> {
    const response = await api.post<VettingCampaign>('/campaigns/', payload);
    return response.data;
  },

  async getDashboard(campaignId: number | string): Promise<CampaignDashboard> {
    const response = await api.get<CampaignDashboard>(`/campaigns/${campaignId}/dashboard/`);
    return response.data;
  },

  async importCandidates(
    campaignId: number | string,
    payload: {
      candidates: CandidateImportRow[];
      send_invites?: boolean;
    }
  ): Promise<CandidateImportResult> {
    const response = await api.post<CandidateImportResult>(
      `/campaigns/${campaignId}/candidates/import/`,
      payload
    );
    return response.data;
  },

  async getEnrollments(campaignId: number | string): Promise<CandidateEnrollment[]> {
    const response = await api.get<PaginatedResponse<CandidateEnrollment> | CandidateEnrollment[]>(
      '/enrollments/',
      { params: { campaign: campaignId } }
    );
    return extractResults(response.data);
  },

  async getInvitations(campaignId: number | string): Promise<Invitation[]> {
    const response = await api.get<PaginatedResponse<Invitation> | Invitation[]>(
      '/invitations/',
      { params: { campaign: campaignId } }
    );
    return extractResults(response.data);
  },
};

