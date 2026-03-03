import api from "./api";
import type {
  ApiError,
  BackgroundCheck,
  BackgroundCheckEvent,
  BackgroundCheckStatus,
  BackgroundCheckType,
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

export interface ListBackgroundChecksParams {
  case_id?: string;
  check_type?: BackgroundCheckType | "all";
  status?: BackgroundCheckStatus | "all";
}

export interface CreateBackgroundCheckPayload {
  case: number;
  check_type: BackgroundCheckType;
  provider_key?: string;
  request_payload?: Record<string, unknown>;
  consent_evidence?: Record<string, unknown>;
  run_async?: boolean;
}

export const backgroundCheckService = {
  async list(params: ListBackgroundChecksParams = {}): Promise<BackgroundCheck[]> {
    try {
      const response = await api.get<PaginatedResponse<BackgroundCheck> | BackgroundCheck[]>(
        "/background-checks/checks/",
        {
          params: {
            ...(params.case_id ? { case_id: params.case_id } : {}),
            ...(params.check_type && params.check_type !== "all" ? { check_type: params.check_type } : {}),
            ...(params.status && params.status !== "all" ? { status: params.status } : {}),
          },
        },
      );
      return extractResults(response.data);
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch background checks"));
    }
  },

  async create(payload: CreateBackgroundCheckPayload): Promise<BackgroundCheck> {
    try {
      const response = await api.post<BackgroundCheck>("/background-checks/checks/", payload);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to create background check"));
    }
  },

  async getById(checkId: string): Promise<BackgroundCheck> {
    try {
      const response = await api.get<BackgroundCheck>(`/background-checks/checks/${checkId}/`);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch background check detail"));
    }
  },

  async refresh(checkId: string): Promise<BackgroundCheck> {
    try {
      const response = await api.post<BackgroundCheck>(`/background-checks/checks/${checkId}/refresh/`, {});
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to refresh background check"));
    }
  },

  async getEvents(checkId: string): Promise<BackgroundCheckEvent[]> {
    try {
      const response = await api.get<BackgroundCheckEvent[]>(`/background-checks/checks/${checkId}/events/`);
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch background check events"));
    }
  },
};
