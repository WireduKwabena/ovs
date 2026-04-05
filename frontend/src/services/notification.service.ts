import api from "./api";
import type { Notification, PaginatedResponse } from "@/types";
import { toServiceError } from "@/utils/apiError";

type NotificationApiRecord = {
  id: string;
  subject?: string;
  title?: string;
  message?: string;
  status?: string;
  is_read?: boolean;
  is_archived?: boolean;
  archived_at?: string;
  metadata?: Record<string, unknown>;
  notification_type?: Notification["notification_type"];
  idempotency_key?: string;
  created_at: string;
  read_at?: string;
  priority?: Notification["priority"];
};

const extractResults = <T>(payload: PaginatedResponse<T> | T[]): T[] => {
  if (Array.isArray(payload)) {
    return payload;
  }
  return Array.isArray(payload.results) ? payload.results : [];
};

const normalizeNotification = (record: NotificationApiRecord): Notification => {
  const isRead = record.is_read ?? record.status === "read";
  const normalizedStatus: Notification["status"] = isRead
    ? "read"
    : record.status === "pending"
      ? "pending"
      : record.status === "sent"
        ? "sent"
        : record.status === "failed"
          ? "failed"
          : record.status === "archived"
            ? "archived"
            : "unread";

  return {
    id: record.id,
    notification_type: record.notification_type ?? "in_app",
    title: record.title || record.subject || "Notification",
    subject: record.subject,
    message: record.message ?? "",
    status: normalizedStatus,
    metadata: (record.metadata as Record<string, unknown>) || {},
    idempotency_key: record.idempotency_key,
    is_read: isRead,
    is_archived: Boolean(record.is_archived),
    archived_at: record.archived_at,
    created_at: record.created_at,
    read_at: record.read_at,
    priority: record.priority,
  };
};


export const notificationService = {
  async getAll(params?: {
    status?: string;
    type?: string;
    priority?: string;
    channel?: "in_app" | "email" | "sms" | "all";
    archived?: "active" | "archived" | "all";
    event_type?: string;
    idempotency_key?: string;
    subsystem?: string;
  }): Promise<Notification[]> {
    try {
      const { archived = "active", ...restParams } = params ?? {};
      const archivedParam =
        archived === "archived"
          ? "only"
          : archived === "all"
            ? "all"
            : "false";
      const response = await api.get<
        PaginatedResponse<NotificationApiRecord> | NotificationApiRecord[]
      >("/notifications/", {
        params: { channel: "in_app", archived: archivedParam, ...restParams },
      });
      return extractResults(response.data).map(normalizeNotification);
    } catch (error) {
      throw toServiceError(error, "Failed to fetch notifications");
    }
  },

  async getById(id: string): Promise<Notification> {
    try {
      const response = await api.get<NotificationApiRecord>(`/notifications/${id}/`, {
        params: { channel: "all", archived: "all" },
      });
      return normalizeNotification(response.data);
    } catch (error) {
      throw toServiceError(error, "Failed to fetch notification detail");
    }
  },

  async getUnreadCount(): Promise<{ unread_count: number }> {
    try {
      const response = await api.get<{ unread_count: number }>("/notifications/unread-count/");
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Failed to fetch count");
    }
  },

  async markAsRead(notificationIds: string[]): Promise<void> {
    try {
      await api.post("/notifications/mark-as-read/", {
        notification_ids: notificationIds,
      });
    } catch (error) {
      throw toServiceError(error, "Failed to mark notifications as read");
    }
  },

  async markAllAsRead(): Promise<void> {
    try {
      await api.post("/notifications/mark-all-as-read/");
    } catch (error) {
      throw toServiceError(error, "Failed to mark all notifications as read");
    }
  },

  async markSingleAsRead(id: string): Promise<void> {
    try {
      await api.post(`/notifications/${id}/mark_read/`);
    } catch (error) {
      throw toServiceError(error, "Failed to mark notification as read");
    }
  },

  async archive(id: string): Promise<void> {
    try {
      await api.delete(`/notifications/${id}/archive/`);
    } catch (error) {
      throw toServiceError(error, "Failed to archive notification");
    }
  },

  async restore(id: string): Promise<void> {
    try {
      await api.post(`/notifications/${id}/restore/`);
    } catch (error) {
      throw toServiceError(error, "Failed to restore notification");
    }
  },
};
