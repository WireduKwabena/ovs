import api from "./api";
import type {
  AiMonitorDocumentClassificationResponse,
  AiMonitorHealthResponse,
  AiMonitorSocialProfileItem,
  AiMonitorSocialProfileResponse,
  ApiError,
} from "@/types";

const toErrorMessage = (error: unknown, fallback: string): string => {
  const responseData = (error as { response?: { data?: ApiError } })?.response?.data;
  return responseData?.message || fallback;
};

export interface AiMonitorHealthParams {
  model_name?: string;
}

export interface ClassifyDocumentPayload {
  file: File;
  document_type?: string;
  top_k?: number;
}

export interface SocialProfileCheckPayload {
  case_id?: string;
  consent_provided: boolean;
  profiles: AiMonitorSocialProfileItem[];
}

export const aiMonitorService = {
  async health(params: AiMonitorHealthParams = {}): Promise<AiMonitorHealthResponse> {
    try {
      const response = await api.get<AiMonitorHealthResponse>("/ai-monitor/health/", {
        params: params.model_name ? { model_name: params.model_name } : {},
      });
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch AI monitor health"));
    }
  },

  async classifyDocument(payload: ClassifyDocumentPayload): Promise<AiMonitorDocumentClassificationResponse> {
    try {
      const formData = new FormData();
      formData.append("file", payload.file);
      if (payload.document_type) {
        formData.append("document_type", payload.document_type);
      }
      if (typeof payload.top_k === "number") {
        formData.append("top_k", String(payload.top_k));
      }

      const response = await api.post<AiMonitorDocumentClassificationResponse>(
        "/ai-monitor/classify-document/",
        formData,
        {
          headers: { "Content-Type": "multipart/form-data" },
        },
      );
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to classify document"));
    }
  },

  async checkSocialProfiles(payload: SocialProfileCheckPayload): Promise<AiMonitorSocialProfileResponse> {
    try {
      const response = await api.post<AiMonitorSocialProfileResponse>(
        "/ai-monitor/check-social-profiles/",
        payload,
      );
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to run social profile checks"));
    }
  },
};
