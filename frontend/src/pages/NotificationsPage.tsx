import React, { useMemo, useState } from "react";
import { Archive, ArrowRight, Copy, Eye, RefreshCw } from "lucide-react";
import { toast } from "react-toastify";
import { Link, useSearchParams } from "react-router-dom";

import "./NotificationsPage.css";
import { Loader } from "@/components/common/Loader";
import { Input } from "@/components/ui/input";
import { useNotifications } from "@/hooks/useNotifications";
import type { Notification } from "@/types";
import { copyTextToClipboard } from "@/utils/helper";
import {
  extractNotificationActions,
  formatNotificationAvailabilityLabel,
  getNotificationActionAvailability,
} from "@/utils/notificationActions";

type StatusFilter = "all" | "unread" | "read" | "archived";
type NotificationChannelFilter = "in_app" | "email" | "sms" | "all";

const NOTIFICATION_CHANNEL_OPTIONS: Array<{
  value: NotificationChannelFilter;
  label: string;
}> = [
  { value: "in_app", label: "In-app only" },
  { value: "all", label: "All channels" },
  { value: "email", label: "Email only" },
  { value: "sms", label: "SMS only" },
];

const normalizeNotificationChannel = (
  value: string | null,
): NotificationChannelFilter => {
  if (value === "all" || value === "email" || value === "sms") {
    return value;
  }
  return "in_app";
};

const normalizeStatusFilter = (value: string | null): StatusFilter => {
  if (value === "unread" || value === "read" || value === "archived") {
    return value;
  }
  return "all";
};

type NotificationTraceFilterFormProps = {
  initialChannel: NotificationChannelFilter;
  initialEventType: string;
  initialIdempotencyKey: string;
  activeSubsystem?: string;
  onApply: (filters: {
    channel: NotificationChannelFilter;
    eventType: string;
    idempotencyKey: string;
  }) => void;
  onClear: () => void;
  disabled?: boolean;
};

const NotificationTraceFilterForm: React.FC<
  NotificationTraceFilterFormProps
> = ({
  initialChannel,
  initialEventType,
  initialIdempotencyKey,
  activeSubsystem,
  onApply,
  onClear,
  disabled = false,
}) => {
  const [channel, setChannel] =
    useState<NotificationChannelFilter>(initialChannel);
  const [eventType, setEventType] = useState(initialEventType);
  const [idempotencyKey, setIdempotencyKey] = useState(initialIdempotencyKey);

  const hasActiveFilters =
    channel !== "in_app" || Boolean(eventType.trim() || idempotencyKey.trim() || activeSubsystem);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onApply({
      channel,
      eventType: eventType.trim(),
      idempotencyKey: idempotencyKey.trim(),
    });
  };

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-slate-900">
          Trace filters
        </h2>
        <p className="mt-1 text-sm text-slate-700">
          Filter notification delivery records by channel, event type, or an
          idempotency key when you need to trace retries and reminders.
        </p>
      </div>

      <form className="space-y-3" onSubmit={handleSubmit}>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="space-y-1.5">
            <span className="text-sm font-medium text-slate-800">
              Delivery channel
            </span>
            <select
              value={channel}
              onChange={(event) =>
                setChannel(
                  normalizeNotificationChannel(event.target.value),
                )
              }
              disabled={disabled}
              className="h-9 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-xs outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {NOTIFICATION_CHANNEL_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-1.5">
            <span className="text-sm font-medium text-slate-800">
              Event type
            </span>
            <Input
              value={eventType}
              onChange={(event) => setEventType(event.target.value)}
              disabled={disabled}
              placeholder="e.g. video_call_reminder"
              autoComplete="off"
            />
          </label>

          <label className="space-y-1.5">
            <span className="text-sm font-medium text-slate-800">
              Idempotency key
            </span>
            <Input
              value={idempotencyKey}
              onChange={(event) => setIdempotencyKey(event.target.value)}
              disabled={disabled}
              placeholder="Paste a trace key"
              autoComplete="off"
            />
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="submit"
            disabled={disabled}
            className="inline-flex items-center rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Apply filters
          </button>
          <button
            type="button"
            onClick={onClear}
            disabled={disabled || !hasActiveFilters}
            className="inline-flex items-center rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Clear filters
          </button>
          {hasActiveFilters ? (
            <span className="text-sm text-slate-700">
              Trace filters active.
            </span>
          ) : (
            <span className="text-sm text-slate-700">
              Default view shows active in-app notifications only.
            </span>
          )}
          {activeSubsystem ? (
            <span className="inline-flex rounded-full border border-cyan-200 bg-cyan-50 px-2 py-1 text-xs font-medium text-cyan-800">
              Subsystem: {activeSubsystem}
            </span>
          ) : null}
        </div>
      </form>
    </section>
  );
};

export const NotificationsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const statusFilter = normalizeStatusFilter(searchParams.get("view"));
  const isArchivedView = statusFilter === "archived";
  const appliedChannel = normalizeNotificationChannel(searchParams.get("channel"));
  const appliedEventType = (searchParams.get("event_type") || "").trim();
  const appliedIdempotencyKey = (searchParams.get("idempotency_key") || "").trim();
  const appliedSubsystem = (searchParams.get("subsystem") || "").trim();

  const notificationFilters = useMemo(
    () => ({
      channel: appliedChannel,
      eventType: appliedEventType || undefined,
      idempotencyKey: appliedIdempotencyKey || undefined,
      subsystem: appliedSubsystem || undefined,
    }),
    [appliedChannel, appliedEventType, appliedIdempotencyKey, appliedSubsystem],
  );

  const activeState = useNotifications({
    archived: "active",
    ...notificationFilters,
  });
  const archivedState = useNotifications({
    archived: "archived",
    ...notificationFilters,
  });

  const [archivingId, setArchivingId] = useState<string | null>(null);
  const [copyingNotificationId, setCopyingNotificationId] = useState<string | null>(null);
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
        (item) =>
          item.notification_type === "in_app" &&
          (item.status === "unread" || !item.is_read),
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
        (item) =>
          item.notification_type === "in_app" &&
          (item.status === "unread" || !item.is_read),
      );
    }
    return notificationsArray.filter(
      (item) => item.notification_type === "in_app" && item.status === "read" && item.is_read,
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

  const handleCopyTraceKey = async (
    notificationId: string,
    idempotencyKey: string,
  ) => {
    if (!idempotencyKey) {
      return;
    }

    setCopyingNotificationId(notificationId);
    try {
      await copyTextToClipboard(idempotencyKey);
      toast.success("Trace key copied.");
    } catch (error: unknown) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to copy trace key.",
      );
    } finally {
      setCopyingNotificationId(null);
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

  const handleApplyTraceFilters = (filters: {
    channel: NotificationChannelFilter;
    eventType: string;
    idempotencyKey: string;
  }) => {
    const nextParams = new URLSearchParams(searchParams);
    if (filters.channel === "in_app") {
      nextParams.delete("channel");
    } else {
      nextParams.set("channel", filters.channel);
    }

    if (filters.eventType) {
      nextParams.set("event_type", filters.eventType);
    } else {
      nextParams.delete("event_type");
    }

    if (filters.idempotencyKey) {
      nextParams.set("idempotency_key", filters.idempotencyKey);
    } else {
      nextParams.delete("idempotency_key");
    }

    setSearchParams(nextParams, { replace: true });
  };

  const handleClearTraceFilters = () => {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("channel");
    nextParams.delete("event_type");
    nextParams.delete("idempotency_key");
    nextParams.delete("subsystem");
    setSearchParams(nextParams, { replace: true });
  };

  const handleStatusFilterChange = (nextFilter: StatusFilter) => {
    const nextParams = new URLSearchParams(searchParams);
    if (nextFilter === "all") {
      nextParams.delete("view");
    } else {
      nextParams.set("view", nextFilter);
    }
    setSearchParams(nextParams, { replace: true });
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
      <div className="mx-auto max-w-5xl space-y-6 px-4 py-8 sm:px-6 lg:px-6 xl:px-8">
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
            {!isArchivedView && appliedChannel === "in_app" && unreadCount > 0 ? (
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
              onClick={() => handleStatusFilterChange("all")}
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
              onClick={() => handleStatusFilterChange("unread")}
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
              onClick={() => handleStatusFilterChange("read")}
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
              onClick={() => handleStatusFilterChange("archived")}
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

        <NotificationTraceFilterForm
          key={`${appliedChannel}|${appliedEventType}|${appliedIdempotencyKey}|${appliedSubsystem}`}
          initialChannel={appliedChannel}
          initialEventType={appliedEventType}
          initialIdempotencyKey={appliedIdempotencyKey}
          activeSubsystem={appliedSubsystem}
          onApply={handleApplyTraceFilters}
          onClear={handleClearTraceFilters}
          disabled={isLoading}
        />

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
                  notification.notification_type === "in_app" &&
                  (notification.status === "unread" || !notification.is_read);
                const actions = extractNotificationActions(notification);
                const primaryAction = actions[0];
                const primaryActionAvailability = primaryAction
                  ? getNotificationActionAvailability(notification, primaryAction)
                  : null;
                const eventType =
                  typeof notification.metadata?.event_type === "string"
                    ? notification.metadata.event_type
                    : "";
                const subsystem =
                  typeof notification.metadata?.subsystem === "string"
                    ? notification.metadata.subsystem
                    : "";

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
                        <h3 className="font-semibold text-gray-900 wrap-break-word">
                          {notification.title ||
                            notification.subject ||
                            "Notification"}
                        </h3>
                        <p
                          className="notification-preview-clamp mt-1 text-slate-800 wrap-break-word whitespace-pre-wrap"
                        >
                          {notification.message}
                        </p>
                        {eventType || notification.idempotency_key ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {eventType ? (
                              <span className="inline-flex rounded-full border border-slate-300 bg-slate-50 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-slate-700">
                                Event: {eventType}
                              </span>
                            ) : null}
                            {subsystem ? (
                              <span className="inline-flex rounded-full border border-cyan-200 bg-cyan-50 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-cyan-800">
                                Subsystem: {subsystem}
                              </span>
                            ) : null}
                            <span className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-emerald-800">
                              Channel: {notification.notification_type}
                            </span>
                            {notification.idempotency_key ? (
                              <button
                                type="button"
                                onClick={() =>
                                  void handleCopyTraceKey(
                                    notification.id,
                                    notification.idempotency_key ?? "",
                                  )
                                }
                                className="inline-flex items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 font-mono text-[11px] text-indigo-800 hover:bg-indigo-100"
                                title="Copy trace key"
                                aria-label="Copy trace key"
                              >
                                <Copy className="h-3 w-3" />
                                {copyingNotificationId === notification.id
                                  ? "Copying..."
                                  : `Key: ${notification.idempotency_key}`}
                              </button>
                            ) : null}
                          </div>
                        ) : null}
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
