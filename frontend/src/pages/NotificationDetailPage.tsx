import React from "react";
import { ArrowLeft, ArrowRight, RefreshCw, RotateCcw, Trash2 } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "react-toastify";

import { Loader } from "@/components/common/Loader";
import { notificationService } from "@/services/notification.service";
import {
  extractNotificationActions,
  extractNotificationContext,
  formatNotificationAvailabilityLabel,
  getNotificationActionAvailability,
} from "@/utils/notificationActions";

const MESSAGE_URL_REGEX = /((?:https?|ftp):\/\/[\w\-._~:/?#[\]@!$&'()*+,;=%]+)/gi;
const URL_ONLY_REGEX = /^(?:https?|ftp):\/\/[\w\-._~:/?#[\]@!$&'()*+,;=%]+$/i;

const splitTrailingPunctuation = (rawUrl: string): { href: string; trailing: string } => {
  const match = rawUrl.match(/[).,!?;:]+$/);
  if (!match) {
    return { href: rawUrl, trailing: "" };
  }
  const trailing = match[0];
  const href = rawUrl.slice(0, -trailing.length);
  return { href, trailing };
};

const linkifyMessage = (message: string): React.ReactNode[] => {
  if (!message) {
    return [""];
  }

  const parts = message.split(MESSAGE_URL_REGEX);
  return parts.map((part, index) => {
    if (!URL_ONLY_REGEX.test(part)) {
      return part;
    }

    const { href, trailing } = splitTrailingPunctuation(part);
    if (!href || !URL_ONLY_REGEX.test(href)) {
      return part;
    }

    return (
      <React.Fragment key={`message-link-${index}`}>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-indigo-700 underline underline-offset-2 hover:text-indigo-800 break-all"
        >
          {href}
        </a>
        {trailing}
      </React.Fragment>
    );
  });
};

export const NotificationDetailPage: React.FC = () => {
  const { notificationId } = useParams<{ notificationId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data, isLoading, isFetching, refetch, error } = useQuery({
    queryKey: ["notification", notificationId],
    enabled: Boolean(notificationId),
    queryFn: async () => {
      if (!notificationId) {
        throw new Error("Notification id is missing.");
      }

      const detail = await notificationService.getById(notificationId);
      if (!detail.is_read) {
        try {
          await notificationService.markSingleAsRead(notificationId);
          await queryClient.invalidateQueries({ queryKey: ["notifications"] });
          return {
            ...detail,
            is_read: true,
            status: "read" as const,
            read_at: detail.read_at ?? new Date().toISOString(),
          };
        } catch (markError) {
          const message =
            markError instanceof Error
              ? markError.message
              : "Failed to update notification read state.";
          toast.error(message);
        }
      }
      return detail;
    },
  });

  const actionButtonsWithState = React.useMemo(
    () => {
      if (!data) {
        return [];
      }
      return extractNotificationActions(data).map((action) => ({
        action,
        availability: getNotificationActionAvailability(data, action),
      }));
    },
    [data],
  );
  const contextFields = data ? extractNotificationContext(data) : [];
  const [isArchiving, setIsArchiving] = React.useState(false);
  const [isRestoring, setIsRestoring] = React.useState(false);

  const handleDelete = async () => {
    if (!notificationId || isArchiving) {
      return;
    }
    setIsArchiving(true);
    try {
      await notificationService.archive(notificationId);
      await queryClient.invalidateQueries({ queryKey: ["notifications"] });
      await queryClient.invalidateQueries({ queryKey: ["notification", notificationId] });
      toast.success("Notification deleted.");
      navigate("/notifications");
    } catch (archiveError) {
      const message =
        archiveError instanceof Error ? archiveError.message : "Failed to delete notification.";
      toast.error(message);
    } finally {
      setIsArchiving(false);
    }
  };

  const handleRestore = async () => {
    if (!notificationId || isRestoring) {
      return;
    }
    setIsRestoring(true);
    try {
      await notificationService.restore(notificationId);
      await queryClient.invalidateQueries({ queryKey: ["notifications"] });
      await queryClient.invalidateQueries({ queryKey: ["notification", notificationId] });
      await refetch();
      toast.success("Notification restored.");
    } catch (restoreError) {
      const message =
        restoreError instanceof Error
          ? restoreError.message
          : "Failed to restore notification.";
      toast.error(message);
    } finally {
      setIsRestoring(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader size="lg" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-4">
          <Link
            to="/notifications"
            className="inline-flex items-center gap-2 text-sm font-medium text-slate-800 hover:text-indigo-700"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to notifications
          </Link>
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-800">
            {error instanceof Error ? error.message : "Failed to load notification detail."}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <Link
            to="/notifications"
            className="inline-flex items-center gap-2 text-sm font-medium text-slate-800 hover:text-indigo-700"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to notifications
          </Link>
          <button
            type="button"
            onClick={() => void refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-slate-800 hover:bg-slate-100 disabled:opacity-60"
          >
            <RefreshCw className={`w-4 h-4 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        <article className="rounded-xl border border-gray-200 bg-white p-6 space-y-5">
          <header className="space-y-2">
            <h1 className="text-2xl font-bold text-gray-900 wrap-break-word">
              {data.title || data.subject || "Notification"}
            </h1>
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-700">
              <span>{new Date(data.created_at).toLocaleString()}</span>
              <span className="inline-flex rounded-full border border-slate-300 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-slate-700">
                {data.is_read ? "Read" : "Unread"}
              </span>
              {data.is_archived ? (
                <span className="inline-flex rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-amber-800">
                  Archived
                </span>
              ) : null}
            </div>
          </header>

          <section className="flex flex-wrap items-center gap-2">
            {data.is_archived ? (
              <button
                type="button"
                onClick={() => void handleRestore()}
                disabled={isRestoring}
                className="inline-flex items-center gap-2 rounded-lg border border-emerald-300 px-3 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-60"
              >
                <RotateCcw className="w-4 h-4" />
                {isRestoring ? "Restoring..." : "Restore"}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void handleDelete()}
                disabled={isArchiving}
                className="inline-flex items-center gap-2 rounded-lg border border-rose-300 px-3 py-2 text-sm font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-60"
              >
                <Trash2 className="w-4 h-4" />
                {isArchiving ? "Deleting..." : "Delete"}
              </button>
            )}
          </section>

          <section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="text-sm text-slate-900 whitespace-pre-wrap wrap-break-word">
              {linkifyMessage(data.message)}
            </p>
          </section>

          {contextFields.length > 0 ? (
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-slate-900">Details</h2>
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {contextFields.map((field) => (
                  <div
                    key={`${field.label}-${field.value}`}
                    className="rounded-md border border-slate-200 bg-white px-3 py-2"
                  >
                    <dt className="text-[11px] uppercase tracking-wide text-slate-600">
                      {field.label}
                    </dt>
                    <dd className="text-sm text-slate-900 wrap-break-word">{field.value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ) : null}

          {actionButtonsWithState.length > 0 ? (
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-slate-900">Relevant actions</h2>
              <div className="flex flex-wrap gap-2 items-center">
                {actionButtonsWithState.map(({ action, availability }) => {
                  const key = `${action.href}-${action.label}`;
                  if (availability.disabled) {
                    return (
                      <div
                        key={key}
                        className="inline-flex items-center gap-2 rounded border border-slate-300 bg-slate-100 px-3 py-2 text-sm font-medium text-slate-500"
                      >
                        <button
                          type="button"
                          disabled
                          title={availability.reason}
                          className="inline-flex items-center gap-1 cursor-not-allowed"
                        >
                          {action.label}
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                        {formatNotificationAvailabilityLabel(availability.availableInMinutes) ? (
                          <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-700">
                            {formatNotificationAvailabilityLabel(availability.availableInMinutes)}
                          </span>
                        ) : null}
                      </div>
                    );
                  }

                  if (action.isExternal) {
                    return (
                      <a
                        key={key}
                        href={action.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 rounded border border-indigo-300 px-3 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-50"
                      >
                        {action.label}
                        <ArrowRight className="w-3.5 h-3.5" />
                      </a>
                    );
                  }

                  return (
                    <Link
                      key={key}
                      to={action.href}
                      className="inline-flex items-center gap-1 rounded border border-indigo-300 px-3 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-50"
                    >
                      {action.label}
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  );
                })}
              </div>
              {actionButtonsWithState.some((item) => item.availability.disabled && item.availability.reason) ? (
                <p className="text-xs text-slate-600">
                  {
                    actionButtonsWithState.find(
                      (item) => item.availability.disabled && item.availability.reason,
                    )?.availability.reason
                  }
                </p>
              ) : null}
            </section>
          ) : null}
        </article>
      </div>
    </div>
  );
};
