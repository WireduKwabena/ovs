// src/store/notificationSlice.ts
import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit';
import { notificationService } from '../services/notification.service';
import type { Notification, ApiError } from '../types';

interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  loading: boolean;
  error: ApiError | null;
}

const initialState: NotificationState = {
  notifications: [],
  unreadCount: 0,
  loading: false,
  error: null,
};

export const fetchNotifications = createAsyncThunk<Notification[], void, { rejectValue: ApiError }>(
  'notifications/fetchAll',
  async (_, { rejectWithValue }) => {
    try {
      return await notificationService.getAll();
    } catch (error: any) {
      return rejectWithValue(error.response?.data || { message: 'Failed to fetch' });
    }
  }
);

export const markAsRead = createAsyncThunk<void, string[], { rejectValue: ApiError }>(
  'notifications/markAsRead',
  async (ids, { rejectWithValue }) => {
    try {
      await notificationService.markAsRead(ids);
    } catch (error: any) {
      return rejectWithValue(error.response?.data || { message: 'Mark read failed' });
    }
  }
);

export const markAllAsRead = createAsyncThunk<void, void, { rejectValue: ApiError }>(
  'notifications/markAllAsRead',
  async (_, { rejectWithValue }) => {
    try {
      await notificationService.markAllAsRead();
    } catch (error: any) {
      return rejectWithValue(error.response?.data || { message: 'Mark all failed' });
    }
  }
);

const notificationSlice = createSlice({
  name: 'notifications',
  initialState,
  reducers: {
    addNotification: (state, action: PayloadAction<Notification>) => {
      state.notifications.unshift(action.payload);  // Add to top
      if (action.payload.status === 'unread') state.unreadCount += 1;
    },
    clearNotifications: (state) => {
      state.notifications = [];
      state.unreadCount = 0;
    },
    updateUnreadCount: (state, action: PayloadAction<number>) => {
      state.unreadCount = action.payload;
    },
    clearError: (state) => { state.error = null; },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchNotifications.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchNotifications.fulfilled, (state, action: PayloadAction<Notification[]>) => {
        // ✅ Ensure we store an array
        state.notifications = Array.isArray(action.payload) ? action.payload : [];
        // ✅ Calculate unread count from both fields
        state.unreadCount = state.notifications.filter(
          n => n.status === 'unread' || !n.is_read
        ).length;
        state.loading = false;
      })

      .addCase(fetchNotifications.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as ApiError;
      state.notifications = []; // Reset to empty array on error
    })
    .addCase(markAsRead.pending, (state) => {
        state.loading = true;
      })

      .addCase(markAsRead.fulfilled, (state, action) => {
        // Optimistically update
        // ✅ FIX: Ensure action.meta.arg is array before using
        const idsToMark = Array.isArray(action.meta.arg) ? action.meta.arg : [];
        state.notifications = state.notifications.map(n => 
          idsToMark.includes(n.id) ? { ...n, status: 'read' as const, is_read: true, read_at: new Date().toISOString() } : n
        );
        state.unreadCount = state.notifications.filter(n => n.status === 'unread'|| !n.is_read).length;
        state.loading = false;
      })
      .addCase(markAsRead.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as ApiError;
      })
      .addCase(markAllAsRead.pending, (state) => {
        state.loading = true;
      })
      .addCase(markAllAsRead.fulfilled, (state) => {
        state.notifications = state.notifications.map(n => ({
          ...n,
          status: 'read' as const,
          is_read: true,
          read_at: new Date().toISOString(),
        }));
        state.unreadCount = 0;
        state.loading = false;
      })
      .addCase(markAllAsRead.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as ApiError;
      });
  },
});

export const { addNotification, updateUnreadCount, clearError,clearNotifications } = notificationSlice.actions;
export default notificationSlice.reducer;
