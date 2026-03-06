import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-toastify";

import { notificationService } from "@/services/notification.service";

type UseNotificationsOptions = {
  archived?: "active" | "archived" | "all";
};

export const useNotifications = (options?: UseNotificationsOptions) => {
  const queryClient = useQueryClient();
  const archived = options?.archived ?? "active";

  const { data: notificationsData, isLoading, refetch } = useQuery({
    queryKey: ["notifications", archived],
    queryFn: () => notificationService.getAll({ archived }),
    refetchInterval: 30000,
    staleTime: 1000 * 60,
  });

  const markAsReadMutation = useMutation({
    mutationFn: (ids: string[]) => notificationService.markAsRead(ids),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (err: unknown) =>
      toast.error(err instanceof Error ? err.message : "Failed to mark as read"),
  });

  const markAllAsReadMutation = useMutation({
    mutationFn: () => notificationService.markAllAsRead(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (err: unknown) =>
      toast.error(err instanceof Error ? err.message : "Failed to mark all as read"),
  });

  const archiveMutation = useMutation({
    mutationFn: (id: string) => notificationService.archive(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void refetch();
    },
    onError: (err: unknown) =>
      toast.error(err instanceof Error ? err.message : "Failed to archive notification"),
  });

  const restoreMutation = useMutation({
    mutationFn: (id: string) => notificationService.restore(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void refetch();
    },
    onError: (err: unknown) =>
      toast.error(err instanceof Error ? err.message : "Failed to restore notification"),
  });

  return {
    notifications: notificationsData || [],
    isLoading,
    markAsRead: markAsReadMutation.mutate,
    markAllAsRead: markAllAsReadMutation.mutate,
    archive: archiveMutation.mutate,
    archiveAsync: archiveMutation.mutateAsync,
    restore: restoreMutation.mutate,
    restoreAsync: restoreMutation.mutateAsync,
    refresh: refetch,
  };
};
