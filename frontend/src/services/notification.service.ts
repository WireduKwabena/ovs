// src/services/notification.service.ts (Enhanced with safety checks)
import api from './api';
import type { Notification, ApiError } from '@/types';

export const notificationService = {
  async getAll(): Promise<Notification[]> {
    try {
      const response = await api.get<Notification[]>('/notifications/');
      console.log('API response for notifications:', response.data);
      
      // ✅ Extract the results array from paginated response
      if (response.data && typeof response.data === 'object' && 'results' in response.data) {
        const notifications = (response.data as any).results;
        console.log('✅ Extracted notifications array:', notifications);
        return Array.isArray(notifications) ? notifications : [];
      }
      
      // Fallback for non-paginated response (just in case)
      if (Array.isArray(response.data)) {
        return response.data;
      }
      
      console.error('Unexpected API response structure:', response.data);
      return [];
    } catch (error: any) {
      console.error('Notification service error:', error);
      throw new Error((error.response?.data as ApiError)?.message || 'Failed to fetch notifications');
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
      await api.post(`/notifications/${id}/mark-read/`);
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