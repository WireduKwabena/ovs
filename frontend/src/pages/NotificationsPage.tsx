import React, { useMemo, useState } from "react";
import { Archive, ArrowRight, Eye, RefreshCw } from "lucide-react";
import { toast } from "react-toastify";
import { Link } from "react-router-dom";

import { Loader } from "@/components/common/Loader";
import { useNotifications } from "@/hooks/useNotifications";
import type { Notification } from "@/types";
import {
  extractNotificationActions,
  formatNotificationAvailabilityLabel,
  getNotificationActionAvailability,
} from "@/utils/notificationActions";

type StatusFilter = "all" | "unread" | "read" | "archived";

const previewClampStyle: React.CSSProperties = {
  display: "-webkit-box",
  WebkitLineClamp: 3,
  WebkitBoxOrient: "vertical",
  overflow: "hidden",
};

export const NotificationsPage: React.FC = () => {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const isArchivedView = statusFilter === "archived";

  const activeState = useNotifications({ archived: "active" });
  const archivedState = useNotifications({ archived: "archived" });

  const [archivingId, setArchivingId] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const activeNotifications = useMemo(() => {
    if (!activeState.notifications) return [];
    return Array.isArray(activeState.notifications)
      ? activeState.notifications
      : [];
  }, [activeState.notifications]);

  const archivedNotifications = useMemo(() => {
    if (!archivedState.notifications) return [];
    return Array.isArray(archivedState.notifications)
      ? archivedState.notifications
      : [];
  }, [archivedState.notifications]);

  const notificationsArray = isArchivedView
    ? archivedNotifications
    : activeNotifications;

  const unreadCount = useMemo(
    () =>
      activeNotifications.filter(
        (item) => item.status === "unread" || !item.is_read,
      ).length,
    [activeNotifications],
  );

  const filteredNotifications = useMemo(() => {
    if (isArchivedView) {
      return archivedNotifications;
    }
    if (statusFilter === "all") return notificationsArray;
    if (statusFilter === "unread") {
      return notificationsArray.filter(
        (item) => item.status === "unread" || !item.is_read,
      );
    }
    return notificationsArray.filter(
      (item) => item.status === "read" && item.is_read,
    );
  }, [archivedNotifications, isArchivedView, notificationsArray, statusFilter]);

  const handleArchive = async (notificationId: string) => {
    setArchivingId(notificationId);
    try {
      await activeState.archiveAsync(notificationId);
      toast.success("Notification deleted.");
    } catch (error: unknown) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to delete notification.",
      );
    } finally {
      setArchivingId(null);
    }
  };

  const handleRestore = async (notificationId: string) => {
    setRestoringId(notificationId);
    try {
      await archivedState.restoreAsync(notificationId);
      toast.success("Notification restored.");
    } catch (error: unknown) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to restore notification.",
      );
    } finally {
      setRestoringId(null);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    if (isArchivedView) {
      await archivedState.refresh();
    } else {
      await activeState.refresh();
    }
    setRefreshing(false);
  };

  const isLoading = isArchivedView
    ? archivedState.isLoading
    : activeState.isLoading;

  if (isLoading && notificationsArray.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader size="lg" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="flex flex-wrap justify-between items-center gap-3">
          <h1 className="text-3xl font-bold text-gray-900">Notifications</h1>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void handleRefresh()}
              disabled={refreshing}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-slate-800 hover:bg-slate-100 disabled:opacity-60"
            >
              <RefreshCw
                className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`}
              />
              Refresh
            </button>
            {!isArchivedView && unreadCount > 0 ? (
              <button
                onClick={() => activeState.markAllAsRead()}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
              >
                Mark All as Read
              </button>
            ) : null}
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
              All ({activeNotifications.length})
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
              Read ({activeNotifications.length - unreadCount})
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter("archived")}
              className={`px-3 py-1.5 rounded-full text-sm border ${
                statusFilter === "archived"
                  ? "bg-indigo-100 border-indigo-300 text-indigo-700"
                  : "bg-white border-slate-700 text-slate-700"
              }`}
            >
              Archived ({archivedNotifications.length})
            </button>
          </div>
        </section>

        <section className="rounded-xl border border-gray-200 bg-white p-4">
          {filteredNotifications.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-slate-700 text-lg">
                No notifications for this filter.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredNotifications.map((notification: Notification) => {
                const isUnread =
                  notification.status === "unread" || !notification.is_read;
                const actions = extractNotificationActions(notification);
                const primaryAction = actions[0];
                const primaryActionAvailability = primaryAction
                  ? getNotificationActionAvailability(notification, primaryAction)
                  : null;

                return (
                  <article
                    key={notification.id}
                    className={`rounded-lg border p-4 ${
                      isArchivedView
                        ? "border-amber-300 bg-amber-50"
                        : isUnread
                          ? "border-blue-300 bg-blue-50"
                          : "border-slate-200 bg-white"
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <h3 className="font-semibold text-gray-900 break-words">
                          {notification.title ||
                            notification.subject ||
                            "Notification"}
                        </h3>
                        <p
                          className="mt-1 text-slate-800 break-words whitespace-pre-wrap"
                          style={previewClampStyle}
                        >
                          {notification.message}
                        </p>
                        <p className="mt-2 text-sm text-slate-700">
                          {new Date(notification.created_at).toLocaleString()}
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        {!isArchivedView && isUnread ? (
                          <button
                            onClick={() =>
                              activeState.markAsRead([notification.id])
                            }
                            className="px-3 py-1 text-sm bg-white text-blue-600 border border-blue-300 rounded hover:bg-blue-100"
                          >
                            Mark as Read
                          </button>
                        ) : null}

                        <Link
                          to={`/notifications/${notification.id}`}
                          className="inline-flex items-center gap-1 rounded border border-slate-700 px-3 py-1 text-sm text-slate-800 hover:bg-slate-100"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          View
                        </Link>

                        {primaryAction ? (
                          primaryActionAvailability?.disabled ? (
                            <div className="inline-flex items-center gap-1 rounded border border-slate-300 bg-slate-100 px-3 py-1 text-sm text-slate-500">
                              <button
                                type="button"
                                disabled
                                title={primaryActionAvailability.reason}
                                className="inline-flex items-center gap-1 cursor-not-allowed"
                              >
                                {primaryAction.label}
                                <ArrowRight className="w-3.5 h-3.5" />
                              </button>
                              {formatNotificationAvailabilityLabel(primaryActionAvailability.availableInMinutes) ? (
                                <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-700">
                                  {formatNotificationAvailabilityLabel(primaryActionAvailability.availableInMinutes)}
                                </span>
                              ) : null}
                            </div>
                          ) : primaryAction.isExternal ? (
                            <a
                              href={primaryAction.href}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 px-3 py-1 text-sm border border-indigo-300 text-indigo-700 rounded hover:bg-indigo-50"
                            >
                              {primaryAction.label}
                              <ArrowRight className="w-3.5 h-3.5" />
                            </a>
                          ) : (
                            <Link
                              to={primaryAction.href}
                              className="inline-flex items-center gap-1 px-3 py-1 text-sm border border-indigo-300 text-indigo-700 rounded hover:bg-indigo-50"
                            >
                              {primaryAction.label}
                              <ArrowRight className="w-3.5 h-3.5" />
                            </Link>
                          )
                        ) : null}

                        {isArchivedView ? (
                          <button
                            type="button"
                            onClick={() => void handleRestore(notification.id)}
                            disabled={restoringId === notification.id}
                            className="inline-flex items-center gap-1 px-3 py-1 text-sm border border-emerald-300 text-emerald-700 rounded hover:bg-emerald-50 disabled:opacity-60"
                          >
                            {restoringId === notification.id
                              ? "Restoring..."
                              : "Restore"}
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => void handleArchive(notification.id)}
                            disabled={archivingId === notification.id}
                            className="inline-flex items-center gap-1 px-3 py-1 text-sm border border-rose-300 text-rose-700 rounded hover:bg-rose-50 disabled:opacity-60"
                          >
                            <Archive className="w-3.5 h-3.5" />
                            {archivingId === notification.id
                              ? "Deleting..."
                              : "Delete"}
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
      </div>
    </div>
  );
};
