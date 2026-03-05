import api from "./api";
import type {
  ApiError,
  CandidateEnrollment,
  CandidateProfile,
  CandidateSocialProfile,
  PaginatedResponse,
} from "@/types";

const extractResults = <T>(payload: PaginatedResponse<T> | T[]): T[] => {
  if (Array.isArray(payload)) {
    return payload;
  }
  return Array.isArray(payload.results) ? payload.results : [];
};

const toErrorMessage = (error: unknown, fallback: string): string => {
  const responseData = (error as { response?: { data?: ApiError } })?.response?.data;
  return responseData?.message || fallback;
};

export const candidateService = {
  async listCandidates(): Promise<CandidateProfile[]> {
    try {
      const response = await api.get<PaginatedResponse<CandidateProfile> | CandidateProfile[]>("/candidates/");
      return extractResults(response.data);
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch candidates"));
    }
  },

  async getCandidateById(candidateId: string): Promise<CandidateProfile> {
    try {
      const response = await api.get<CandidateProfile>(`/candidates/${candidateId}/`);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch candidate detail"));
    }
  },

  async createCandidate(payload: Partial<CandidateProfile>): Promise<CandidateProfile> {
    try {
      const response = await api.post<CandidateProfile>("/candidates/", payload);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to create candidate"));
    }
  },

  async updateCandidate(candidateId: string, payload: Partial<CandidateProfile>): Promise<CandidateProfile> {
    try {
      const response = await api.patch<CandidateProfile>(`/candidates/${candidateId}/`, payload);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to update candidate"));
    }
  },

  async deleteCandidate(candidateId: string): Promise<void> {
    try {
      await api.delete(`/candidates/${candidateId}/`);
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to delete candidate"));
    }
  },

  async listSocialProfiles(params?: {
    candidate?: string;
    platform?: string;
  }): Promise<CandidateSocialProfile[]> {
    try {
      const response = await api.get<PaginatedResponse<CandidateSocialProfile> | CandidateSocialProfile[]>(
        "/social-profiles/",
        { params },
      );
      return extractResults(response.data);
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch social profiles"));
    }
  },

  async getSocialProfileById(profileId: string): Promise<CandidateSocialProfile> {
    try {
      const response = await api.get<CandidateSocialProfile>(`/social-profiles/${profileId}/`);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch social profile detail"));
    }
  },

  async createSocialProfile(payload: Partial<CandidateSocialProfile>): Promise<CandidateSocialProfile> {
    try {
      const response = await api.post<CandidateSocialProfile>("/social-profiles/", payload);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to create social profile"));
    }
  },

  async updateSocialProfile(
    profileId: string,
    payload: Partial<CandidateSocialProfile>,
  ): Promise<CandidateSocialProfile> {
    try {
      const response = await api.patch<CandidateSocialProfile>(`/social-profiles/${profileId}/`, payload);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to update social profile"));
    }
  },

  async deleteSocialProfile(profileId: string): Promise<void> {
    try {
      await api.delete(`/social-profiles/${profileId}/`);
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to delete social profile"));
    }
  },

  async listEnrollments(params?: {
    campaign?: string;
    status?: string;
  }): Promise<CandidateEnrollment[]> {
    try {
      const response = await api.get<PaginatedResponse<CandidateEnrollment> | CandidateEnrollment[]>(
        "/enrollments/",
        { params },
      );
      return extractResults(response.data);
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch enrollments"));
    }
  },

  async getEnrollmentById(enrollmentId: string): Promise<CandidateEnrollment> {
    try {
      const response = await api.get<CandidateEnrollment>(`/enrollments/${enrollmentId}/`);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch enrollment detail"));
    }
  },

  async createEnrollment(payload: Partial<CandidateEnrollment>): Promise<CandidateEnrollment> {
    try {
      const response = await api.post<CandidateEnrollment>("/enrollments/", payload);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to create enrollment"));
    }
  },

  async markEnrollmentComplete(enrollmentId: string): Promise<CandidateEnrollment> {
    try {
      const response = await api.post<CandidateEnrollment>(`/enrollments/${enrollmentId}/mark-complete/`, {});
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to mark enrollment complete"));
    }
  },
};
