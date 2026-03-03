// src/services/notification.service.ts (Enhanced with safety checks)
import api from './api';
import type { Notification, ApiError, PaginatedResponse } from '@/types';

const extractResults = <T>(payload: PaginatedResponse<T> | T[]): T[] => {
  if (Array.isArray(payload)) {
    return payload;
  }
  return Array.isArray(payload.results) ? payload.results : [];
};

export const notificationService = {
  async getAll(params?: {
    status?: string;
    type?: string;
    priority?: string;
  }): Promise<Notification[]> {
    try {
      const response = await api.get<PaginatedResponse<Notification> | Notification[]>(
        '/notifications/',
        { params },
      );
      return extractResults(response.data);
    } catch (error: any) {
      console.error('Notification service error:', error);
      throw new Error((error.response?.data as ApiError)?.message || 'Failed to fetch notifications');
    }
  },

  async getById(id: number): Promise<Notification> {
    try {
      const response = await api.get<Notification>(`/notifications/${id}/`);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Failed to fetch notification detail');
    }
  },

  async getUnreadCount(): Promise<{ unread_count: number }> {
    try {
      const response = await api.get('/notifications/unread-count/');
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Failed to fetch count');
    }
  },

  async markAsRead(notificationIds: number[]): Promise<void> {
    try {
      console.log('Marking as read:', notificationIds);
      await api.post('/notifications/mark-as-read/', {
        notification_ids: notificationIds,
      });
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Mark read failed');
    }
  },

  async markAllAsRead(): Promise<void> {
    try {
      console.log('Marking all as read');
      await api.post('/notifications/mark-all-as-read/');
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Mark all failed');
    }
  },

  async markSingleAsRead(id: number): Promise<void> {
    try {
      await api.post(`/notifications/${id}/mark_read/`);
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Mark single failed');
    }
  },

  async archive(id: number): Promise<void> {
    try {
      await api.delete(`/notifications/${id}/archive/`);
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Archive failed');
    }
  },
};
