// src/hooks/useNotifications.ts (Fixed - Resolves All Errors)
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useDispatch } from 'react-redux';
import type { AppDispatch } from '@/app/store';  // Adjust path if needed
import {  fetchNotifications, markAllAsRead, markAsRead } from '@/store/notificationSlice';  // Ensure slice exports these (as per prior tweaks)
import { notificationService } from '@/services/notification.service';
import { useEffect } from 'react';
import { toast } from 'react-toastify';

export const useNotifications = () => {
  const dispatch = useDispatch<AppDispatch>();
  const queryClient = useQueryClient();

  const { data: notificationsData, isLoading } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => notificationService.getAll(),
    refetchInterval: 30000, // Poll every 30 seconds
    staleTime: 1000 * 60,  // 1 min stale
  });

  useEffect(() => {
    if (notificationsData) {
      dispatch(fetchNotifications());  // Sync RTQ data to Redux (or let thunk handle fetch)
    }
  }, [notificationsData, dispatch]);

  const markAsReadMutation = useMutation({
    mutationFn: (ids: number[]) => notificationService.markAsRead(ids),
    onSuccess: (_, variables: number[]) => {  // Use variables (ids) from mutation arg
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      dispatch(markAsRead(variables));  // Pass ids via variables
    },
    onError: (err) => toast.error(err.message || 'Failed to mark as read'),  // Use err.message
  });

  const markAllAsReadMutation = useMutation({
    mutationFn: () => notificationService.markAllAsRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      dispatch(markAllAsRead());  // Redux thunk/action
    },
    onError: (err) => toast.error(err.message || 'Failed to mark all as read'),  // Use err.message
  });

  return {
    notifications: notificationsData || [],
    isLoading,
    markAsRead: markAsReadMutation.mutate,
    markAllAsRead: markAllAsReadMutation.mutate,
  };
};