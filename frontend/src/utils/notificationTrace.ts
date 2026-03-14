export type NotificationTraceChannel = "in_app" | "email" | "sms" | "all";
export type NotificationTraceView = "all" | "unread" | "read" | "archived";

interface BuildNotificationTraceHrefParams {
  channel?: NotificationTraceChannel;
  eventType?: string;
  idempotencyKey?: string;
  subsystem?: string;
  view?: NotificationTraceView;
}

export const buildNotificationTraceHref = ({
  channel = "all",
  eventType,
  idempotencyKey,
  subsystem,
  view = "all",
}: BuildNotificationTraceHrefParams = {}): string => {
  const params = new URLSearchParams();

  if (channel !== "in_app") {
    params.set("channel", channel);
  }

  if (eventType) {
    params.set("event_type", eventType);
  }

  if (idempotencyKey) {
    params.set("idempotency_key", idempotencyKey);
  }

  if (subsystem) {
    params.set("subsystem", subsystem);
  }

  if (view !== "all") {
    params.set("view", view);
  }

  const query = params.toString();
  return query ? `/notifications?${query}` : "/notifications";
};

export const buildReminderNotificationTraceHref = (
  view: NotificationTraceView = "all",
): string =>
  buildNotificationTraceHref({
    channel: "all",
    eventType: "video_call_reminder",
    view,
  });

export const buildProcessingErrorNotificationTraceHref = (
  view: NotificationTraceView = "all",
): string =>
  buildNotificationTraceHref({
    channel: "all",
    eventType: "processing_error",
    view,
  });

export const buildBillingProcessingErrorNotificationTraceHref = (
  view: NotificationTraceView = "all",
): string =>
  buildNotificationTraceHref({
    channel: "all",
    eventType: "processing_error",
    subsystem: "billing",
    view,
  });

export const buildBillingPaymentFailureNotificationTraceHref = (
  view: NotificationTraceView = "all",
): string =>
  buildNotificationTraceHref({
    channel: "all",
    eventType: "billing_payment_failed",
    subsystem: "billing",
    view,
  });
