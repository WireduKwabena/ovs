import api from "./api";
import type { ApiError, MLModelMetrics, MLPerformanceSummary, PaginatedResponse } from "@/types";

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

export const mlMonitoringService = {
  async list(modelName?: string): Promise<MLModelMetrics[]> {
    try {
      const response = await api.get<PaginatedResponse<MLModelMetrics> | MLModelMetrics[]>("/ml-monitoring/", {
        params: modelName ? { model_name: modelName } : {},
      });
      return extractResults(response.data);
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch model metrics"));
    }
  },

  async latest(): Promise<MLModelMetrics[]> {
    try {
      const response = await api.get<MLModelMetrics[]>("/ml-monitoring/latest/");
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch latest model metrics"));
    }
  },

  async performanceSummary(): Promise<MLPerformanceSummary> {
    try {
      const response = await api.get<MLPerformanceSummary>("/ml-monitoring/performance-summary/");
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch performance summary"));
    }
  },

  async history(modelName: string, limit = 10): Promise<MLModelMetrics[]> {
    try {
      const response = await api.get<{ model_name: string; history: MLModelMetrics[]; limit: number }>(
        "/ml-monitoring/history/",
        { params: { model_name: modelName, limit } },
      );
      return Array.isArray(response.data.history) ? response.data.history : [];
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch model history"));
    }
  },

  async getById(metricId: string): Promise<MLModelMetrics> {
    try {
      const response = await api.get<MLModelMetrics>(`/ml-monitoring/${metricId}/`);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch metric detail"));
    }
  },
};
