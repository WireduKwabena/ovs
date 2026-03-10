import api from "./api";
import type {
  ApiError,
  AuditEventCatalogItem,
  AuditLog,
  AuditStatistics,
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

export interface AuditListParams {
  action?: string;
  entity_type?: string;
  entity_id?: string;
  changes__event?: string;
  search?: string;
  ordering?: string;
}

export const auditService = {
  async list(params: AuditListParams = {}): Promise<AuditLog[]> {
    try {
      const response = await api.get<PaginatedResponse<AuditLog> | AuditLog[]>("/audit/logs/", { params });
      return extractResults(response.data);
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch audit logs"));
    }
  },

  async getRecentActivity(): Promise<AuditLog[]> {
    try {
      const response = await api.get<AuditLog[]>("/audit/logs/recent-activity/");
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch recent audit activity"));
    }
  },

  async getByEntity(entityType: string, entityId: string): Promise<AuditLog[]> {
    try {
      const response = await api.get<AuditLog[]>("/audit/logs/by-entity/", {
        params: { entity_type: entityType, entity_id: entityId },
      });
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch entity audit logs"));
    }
  },

  async getByUser(userId: string): Promise<AuditLog[]> {
    try {
      const response = await api.get<AuditLog[]>("/audit/logs/by-user/", {
        params: { user_id: userId },
      });
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch user audit logs"));
    }
  },

  async getById(logId: string): Promise<AuditLog> {
    try {
      const response = await api.get<AuditLog>(`/audit/logs/${logId}/`);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch audit log detail"));
    }
  },

  async getStatistics(): Promise<AuditStatistics> {
    try {
      const response = await api.get<AuditStatistics>("/audit/logs/statistics/");
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch audit statistics"));
    }
  },

  async getEventCatalog(): Promise<AuditEventCatalogItem[]> {
    try {
      const response = await api.get<PaginatedResponse<AuditEventCatalogItem> | AuditEventCatalogItem[]>(
        "/audit/logs/event-catalog/",
      );
      return extractResults(response.data);
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch audit event catalog"));
    }
  },
};
