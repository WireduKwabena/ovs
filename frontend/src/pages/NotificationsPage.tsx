import React, { useMemo, useState } from "react";
import { Archive, Eye, RefreshCw } from "lucide-react";
import { toast } from "react-toastify";
import { useNavigate } from "react-router-dom";

import { Loader } from "@/components/common/Loader";
import { useNotifications } from "@/hooks/useNotifications";
import { notificationService } from "@/services/notification.service";
import type { Notification } from "@/types";

type StatusFilter = "all" | "unread" | "read";

export const NotificationsPage: React.FC = () => {
  const navigate = useNavigate();
  const { notifications, isLoading, markAsRead, markAllAsRead, archiveAsync, refresh } = useNotifications();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [selectedNotification, setSelectedNotification] = useState<Notification | null>(null);
  const [loadingDetailId, setLoadingDetailId] = useState<number | null>(null);
  const [archivingId, setArchivingId] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const notificationsArray = useMemo(() => {
    if (!notifications) return [];
    return Array.isArray(notifications) ? notifications : [];
  }, [notifications]);

  const filteredNotifications = useMemo(() => {
    if (statusFilter === "all") {
      return notificationsArray;
    }
    if (statusFilter === "unread") {
      return notificationsArray.filter((item) => item.status === "unread" || !item.is_read);
    }
    return notificationsArray.filter((item) => item.status === "read" && item.is_read);
  }, [notificationsArray, statusFilter]);

  const unreadCount = useMemo(
    () => notificationsArray.filter((item) => item.status === "unread" || !item.is_read).length,
    [notificationsArray],
  );

  const extractMeetingId = (notification: Notification): string | null => {
    const meetingId = notification?.metadata?.meeting_id;
    if (!meetingId) {
      return null;
    }
    return String(meetingId);
  };

  const getMeetingLinkFromMetadata = (
    notification: Notification,
    autojoin = true,
  ): string | null => {
    const metadata = notification?.metadata as Record<string, unknown> | undefined;
    if (!metadata) {
      return null;
    }
    const primary = autojoin ? metadata.meeting_autojoin_url : metadata.meeting_url;
    const fallback = autojoin ? metadata.meeting_url : metadata.meeting_autojoin_url;
    if (typeof primary === "string" && primary.trim()) {
      return primary;
    }
    if (typeof fallback === "string" && fallback.trim()) {
      return fallback;
    }
    return null;
  };

  const openMeeting = (notification: Notification, autojoin = true) => {
    const metadataUrl = getMeetingLinkFromMetadata(notification, autojoin);
    if (metadataUrl) {
      try {
        const parsed = new URL(metadataUrl, window.location.origin);
        if (parsed.origin === window.location.origin) {
          navigate(`${parsed.pathname}${parsed.search}`);
          return;
        }
        window.open(parsed.toString(), "_blank", "noopener,noreferrer");
        return;
      } catch {
        // fallback to query-based route
      }
    }
    const meetingId = extractMeetingId(notification);
    if (!meetingId) {
      return;
    }
    const params = new URLSearchParams({ meeting: meetingId, autojoin: autojoin ? "1" : "0" });
    navigate(`/video-calls?${params.toString()}`);
  };

  const handleViewDetail = async (notificationId: number) => {
    setLoadingDetailId(notificationId);
    try {
      const detail = await notificationService.getById(notificationId);
      setSelectedNotification(detail);
      if (detail.status === "unread" || !detail.is_read) {
        markAsRead([notificationId]);
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to load notification detail.";
      toast.error(message);
    } finally {
      setLoadingDetailId(null);
    }
  };

  const handleArchive = async (notificationId: number) => {
    setArchivingId(notificationId);
    try {
      await archiveAsync(notificationId);
      if (selectedNotification?.id === notificationId) {
        setSelectedNotification(null);
      }
      toast.success("Notification archived.");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to archive notification.";
      toast.error(message);
    } finally {
      setArchivingId(null);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await refresh();
    setRefreshing(false);
  };

  if (isLoading && notificationsArray.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader size="lg" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="flex flex-wrap justify-between items-center gap-3">
          <h1 className="text-3xl font-bold text-gray-900">Notifications</h1>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void handleRefresh()}
              disabled={refreshing}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-slate-800 hover:bg-slate-100 disabled:opacity-60"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
              Refresh
            </button>
            {unreadCount > 0 && (
              <button
                onClick={() => markAllAsRead()}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
              >
                Mark All as Read
              </button>
            )}
          </div>
        </div>

        <section className="rounded-xl border border-gray-200 bg-white p-4">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setStatusFilter("all")}
              className={`px-3 py-1.5 rounded-full text-sm border ${
                statusFilter === "all"
                  ? "bg-indigo-100 border-indigo-300 text-indigo-700"
                  : "bg-white border-slate-700 text-slate-700"
              }`}
            >
              All ({notificationsArray.length})
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter("unread")}
              className={`px-3 py-1.5 rounded-full text-sm border ${
                statusFilter === "unread"
                  ? "bg-indigo-100 border-indigo-300 text-indigo-700"
                  : "bg-white border-slate-700 text-slate-700"
              }`}
            >
              Unread ({unreadCount})
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter("read")}
              className={`px-3 py-1.5 rounded-full text-sm border ${
                statusFilter === "read"
                  ? "bg-indigo-100 border-indigo-300 text-indigo-700"
                  : "bg-white border-slate-700 text-slate-700"
              }`}
            >
              Read ({notificationsArray.length - unreadCount})
            </button>
          </div>
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <section className="lg:col-span-2 rounded-xl border border-gray-200 bg-white p-4">
            {filteredNotifications.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-slate-700 text-lg">No notifications for this filter.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredNotifications.map((notification) => {
                  const isUnread = notification.status === "unread" || !notification.is_read;
                  const meetingId = extractMeetingId(notification);
                  return (
                    <article
                      key={notification.id}
                      className={`rounded-lg border p-4 ${
                        isUnread ? "border-blue-300 bg-blue-50" : "border-slate-200 bg-white"
                      }`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="flex-1">
                          <h3 className="font-semibold text-gray-900">{notification.title}</h3>
                          <p className="mt-1 text-slate-800">{notification.message}</p>
                          <p className="mt-2 text-sm text-slate-700">
                            {new Date(notification.created_at).toLocaleString()}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          {isUnread && (
                            <button
                              onClick={() => markAsRead([notification.id])}
                              className="px-3 py-1 text-sm bg-white text-blue-600 border border-blue-300 rounded hover:bg-blue-100"
                            >
                              Mark as Read
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => void handleViewDetail(notification.id)}
                            disabled={loadingDetailId === notification.id}
                            className="inline-flex items-center gap-1 rounded border border-slate-700 px-3 py-1 text-sm text-slate-800 hover:bg-slate-100 disabled:opacity-60"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            {loadingDetailId === notification.id ? "Loading..." : "View"}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleArchive(notification.id)}
                            disabled={archivingId === notification.id}
                            className="inline-flex items-center gap-1 px-3 py-1 text-sm border border-rose-300 text-rose-700 rounded hover:bg-rose-50 disabled:opacity-60"
                          >
                            <Archive className="w-3.5 h-3.5" />
                            {archivingId === notification.id ? "Archiving..." : "Archive"}
                          </button>
                          {meetingId && (
                            <button
                              type="button"
                              onClick={() => openMeeting(notification, true)}
                              className="inline-flex items-center gap-1 px-3 py-1 text-sm border border-indigo-300 text-indigo-700 rounded hover:bg-indigo-50"
                            >
                              Open Meeting
                            </button>
                          )}
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>

          <section className="rounded-xl border border-gray-200 bg-white p-4">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Notification Detail</h2>
            {!selectedNotification ? (
              <p className="text-sm text-slate-700">Select a notification to inspect full details.</p>
            ) : (
              <div className="space-y-3">
                <div>
                  <p className="text-xs uppercase text-slate-700">Title</p>
                  <p className="text-sm font-medium text-gray-900">{selectedNotification.title}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-slate-700">Message</p>
                  <p className="text-sm text-gray-800 whitespace-pre-wrap">{selectedNotification.message}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-slate-700">Type</p>
                  <p className="text-sm text-gray-800">{selectedNotification.notification_type}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-slate-700">Status</p>
                  <p className="text-sm text-gray-800">{selectedNotification.status}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-slate-700">Metadata</p>
                  <pre className="overflow-auto rounded border border-slate-200 bg-slate-50 p-2 text-xs text-slate-800">
                    {JSON.stringify(selectedNotification.metadata || {}, null, 2)}
                  </pre>
                </div>
                {extractMeetingId(selectedNotification) && (
                  <button
                    type="button"
                    onClick={() => openMeeting(selectedNotification, true)}
                    className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700"
                  >
                    Open related meeting
                  </button>
                )}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
};
