import api from "./api";
import type {
  ApiError,
  ConsistencyCheckApiResult,
  ConsistencyStatistics,
  FraudDetectionApiResult,
  FraudStatistics,
  PaginatedResponse,
  SocialProfileCheckApiResult,
  SocialProfileStatistics,
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

export interface FraudListParams {
  case_id?: string;
  risk_level?: "high" | "medium" | "low" | "all";
}

export interface ConsistencyListParams {
  case_id?: string;
  consistent?: "true" | "false" | "all";
}

export const fraudService = {
  async listFraudResults(params: FraudListParams = {}): Promise<FraudDetectionApiResult[]> {
    try {
      const response = await api.get<PaginatedResponse<FraudDetectionApiResult> | FraudDetectionApiResult[]>(
        "/fraud/results/",
        {
          params: {
            ...(params.case_id ? { case_id: params.case_id } : {}),
            ...(params.risk_level && params.risk_level !== "all" ? { risk_level: params.risk_level } : {}),
          },
        },
      );
      return extractResults(response.data);
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch fraud results"));
    }
  },

  async getFraudStatistics(): Promise<FraudStatistics> {
    try {
      const response = await api.get<FraudStatistics>("/fraud/results/statistics/");
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch fraud statistics"));
    }
  },

  async getFraudResultById(resultId: string): Promise<FraudDetectionApiResult> {
    try {
      const response = await api.get<FraudDetectionApiResult>(`/fraud/results/${resultId}/`);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch fraud result detail"));
    }
  },

  async listConsistencyResults(params: ConsistencyListParams = {}): Promise<ConsistencyCheckApiResult[]> {
    try {
      const response = await api.get<PaginatedResponse<ConsistencyCheckApiResult> | ConsistencyCheckApiResult[]>(
        "/fraud/consistency/",
        {
          params: {
            ...(params.case_id ? { case_id: params.case_id } : {}),
            ...(params.consistent && params.consistent !== "all" ? { consistent: params.consistent } : {}),
          },
        },
      );
      return extractResults(response.data);
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch consistency results"));
    }
  },

  async getConsistencyStatistics(): Promise<ConsistencyStatistics> {
    try {
      const response = await api.get<ConsistencyStatistics>("/fraud/consistency/statistics/");
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch consistency statistics"));
    }
  },

  async getConsistencyResultById(resultId: string): Promise<ConsistencyCheckApiResult> {
    try {
      const response = await api.get<ConsistencyCheckApiResult>(`/fraud/consistency/${resultId}/`);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch consistency result detail"));
    }
  },

  async getConsistencyHistory(limit = 20): Promise<ConsistencyCheckApiResult[]> {
    try {
      const response = await api.get<{ history: ConsistencyCheckApiResult[]; limit: number }>(
        "/fraud/consistency/history/",
        { params: { limit } },
      );
      return Array.isArray(response.data.history) ? response.data.history : [];
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch consistency history"));
    }
  },

  async listSocialProfileResults(params: FraudListParams = {}): Promise<SocialProfileCheckApiResult[]> {
    try {
      const response = await api.get<PaginatedResponse<SocialProfileCheckApiResult> | SocialProfileCheckApiResult[]>(
        "/fraud/social-profiles/",
        {
          params: {
            ...(params.case_id ? { case_id: params.case_id } : {}),
            ...(params.risk_level && params.risk_level !== "all" ? { risk_level: params.risk_level } : {}),
          },
        },
      );
      return extractResults(response.data);
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch social profile results"));
    }
  },

  async getSocialProfileStatistics(): Promise<SocialProfileStatistics> {
    try {
      const response = await api.get<SocialProfileStatistics>("/fraud/social-profiles/statistics/");
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch social profile statistics"));
    }
  },

  async getSocialProfileResultById(resultId: string): Promise<SocialProfileCheckApiResult> {
    try {
      const response = await api.get<SocialProfileCheckApiResult>(`/fraud/social-profiles/${resultId}/`);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch social profile result detail"));
    }
  },
};
