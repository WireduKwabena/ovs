import type { Notification } from "@/types";

export type NotificationAction = {
  href: string;
  label: string;
  isExternal: boolean;
};

export type NotificationActionAvailability = {
  disabled: boolean;
  reason?: string;
  availableInMinutes?: number;
};

export type NotificationContextField = {
  label: string;
  value: string;
};

const URL_PATTERN = /https?:\/\/[^\s<>"']+/gi;
const DEFAULT_ALLOW_JOIN_BEFORE_SECONDS = 300;
const CLOSED_EVENT_TYPES = new Set(["video_call_time_up", "video_call_cancelled"]);
const CLOSED_MEETING_STATUSES = new Set(["cancelled", "completed", "closed"]);
const CLOSED_MESSAGE_PATTERNS = [
  /time is up/i,
  /window has been closed/i,
  /meeting ended/i,
  /meeting has ended/i,
  /cancelled/i,
];

const KEYWORD_LABELS: Array<{ match: RegExp; label: string }> = [
  { match: /(meeting_autojoin|autojoin|join_call|video_call|livekit|heygen)/i, label: "Join video call" },
  { match: /(meeting_url|join_url|join_link|join)/i, label: "Join" },
  { match: /(interview)/i, label: "Start interview" },
  { match: /(case|application)/i, label: "Open case" },
  { match: /(dashboard)/i, label: "Open dashboard" },
];

const inferLabel = (keyHint: string): string => {
  for (const item of KEYWORD_LABELS) {
    if (item.match.test(keyHint)) {
      return item.label;
    }
  }
  return "Open link";
};

const isAbsoluteUrl = (value: string): boolean => /^https?:\/\//i.test(value);

const toUiHref = (rawHref: string): { href: string; isExternal: boolean } => {
  const trimmed = rawHref.trim();
  if (!trimmed) {
    return { href: "", isExternal: false };
  }

  if (trimmed.startsWith("/")) {
    return { href: trimmed, isExternal: false };
  }

  if (!isAbsoluteUrl(trimmed)) {
    return { href: "", isExternal: false };
  }

  try {
    const parsed = new URL(trimmed);
    if (typeof window !== "undefined" && parsed.origin === window.location.origin) {
      return { href: `${parsed.pathname}${parsed.search}${parsed.hash}`, isExternal: false };
    }
    return { href: parsed.toString(), isExternal: true };
  } catch {
    return { href: "", isExternal: false };
  }
};

const collectMetadataUrlCandidates = (
  value: unknown,
  keyPath: string,
  out: Array<{ key: string; value: string }>,
): void => {
  if (value == null) {
    return;
  }

  if (typeof value === "string") {
    const trimmed = value.trim();
    if (trimmed.startsWith("/") || isAbsoluteUrl(trimmed)) {
      out.push({ key: keyPath, value: trimmed });
    }
    return;
  }

  if (Array.isArray(value)) {
    value.forEach((item, index) => collectMetadataUrlCandidates(item, `${keyPath}[${index}]`, out));
    return;
  }

  if (typeof value === "object") {
    Object.entries(value as Record<string, unknown>).forEach(([key, nestedValue]) => {
      const nextKeyPath = keyPath ? `${keyPath}.${key}` : key;
      collectMetadataUrlCandidates(nestedValue, nextKeyPath, out);
    });
  }
};

const collectMessageUrls = (message: string): Array<{ key: string; value: string }> => {
  const matches = message.match(URL_PATTERN) ?? [];
  return matches.map((value, index) => ({ key: `message_url_${index + 1}`, value }));
};

const PRIORITY_CONTEXT_KEYS = [
  "case_id",
  "event_type",
  "meeting_id",
  "old_status",
  "new_status",
  "document_type",
  "document_status",
  "recommendation",
  "score",
] as const;

const prettifyKey = (rawKey: string): string =>
  rawKey
    .replace(/_/g, " ")
    .replace(/\./g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());

const isDisplayableScalar = (value: unknown): value is string | number | boolean => {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 && !trimmed.startsWith("{") && !trimmed.startsWith("[");
  }
  return typeof value === "number" || typeof value === "boolean";
};

const isUrlValue = (value: string): boolean => value.startsWith("/") || isAbsoluteUrl(value);

const parseTimestamp = (value: unknown): Date | null => {
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed;
};

const isJoinAction = (action: NotificationAction): boolean => {
  const label = action.label.toLowerCase();
  const href = action.href.toLowerCase();
  return (
    label.includes("join") ||
    label.includes("interview") ||
    href.includes("/video-calls") ||
    href.includes("/interview/")
  );
};

export const extractNotificationActions = (
  notification: Pick<Notification, "metadata" | "message">,
): NotificationAction[] => {
  const candidates: Array<{ key: string; value: string }> = [];
  collectMetadataUrlCandidates(notification.metadata || {}, "", candidates);
  candidates.push(...collectMessageUrls(notification.message || ""));

  const seen = new Set<string>();
  const actions: NotificationAction[] = [];

  for (const candidate of candidates) {
    const target = toUiHref(candidate.value);
    if (!target.href || seen.has(target.href)) {
      continue;
    }

    seen.add(target.href);
    actions.push({
      href: target.href,
      label: inferLabel(candidate.key),
      isExternal: target.isExternal,
    });
  }

  return actions;
};

export const getNotificationActionAvailability = (
  notification: Pick<Notification, "message" | "metadata">,
  action: NotificationAction,
): NotificationActionAvailability => {
  if (!isJoinAction(action)) {
    return { disabled: false };
  }

  const metadata = notification.metadata || {};
  const eventType = String(metadata.event_type || "").toLowerCase();
  const meetingStatus = String(metadata.meeting_status || "").toLowerCase();
  const message = String(notification.message || "");

  const isClosedByEvent =
    CLOSED_EVENT_TYPES.has(eventType) ||
    CLOSED_MEETING_STATUSES.has(meetingStatus) ||
    CLOSED_MESSAGE_PATTERNS.some((pattern) => pattern.test(message));
  if (isClosedByEvent) {
    return {
      disabled: true,
      reason: "This meeting is closed. Joining is no longer available.",
    };
  }

  const scheduledStart = parseTimestamp(metadata.scheduled_start);
  if (!scheduledStart) {
    return { disabled: false };
  }

  const rawJoinLeadSeconds = Number(metadata.allow_join_before_seconds);
  const allowJoinBeforeSeconds =
    Number.isFinite(rawJoinLeadSeconds) && rawJoinLeadSeconds >= 0
      ? rawJoinLeadSeconds
      : DEFAULT_ALLOW_JOIN_BEFORE_SECONDS;
  const joinWindowStart = new Date(scheduledStart.getTime() - allowJoinBeforeSeconds * 1000);

  if (Date.now() < joinWindowStart.getTime()) {
    const minutesUntil = Math.max(
      1,
      Math.ceil((joinWindowStart.getTime() - Date.now()) / (60 * 1000)),
    );
    return {
      disabled: true,
      reason: `Join will be available at ${joinWindowStart.toLocaleString()}.`,
      availableInMinutes: minutesUntil,
    };
  }

  return { disabled: false };
};

export const formatNotificationAvailabilityLabel = (
  minutes?: number,
): string | null => {
  if (minutes == null) {
    return null;
  }

  const totalMinutes = Math.max(1, Math.ceil(minutes));
  const hours = Math.floor(totalMinutes / 60);
  const remainingMinutes = totalMinutes % 60;

  if (hours === 0) {
    return `Available in ${totalMinutes}m`;
  }

  if (remainingMinutes === 0) {
    return `Available in ${hours}h`;
  }

  return `Available in ${hours}h ${remainingMinutes}m`;
};

export const extractNotificationContext = (
  notification: Pick<Notification, "metadata">,
): NotificationContextField[] => {
  const metadata = notification.metadata || {};
  const fields: NotificationContextField[] = [];
  const seenLabels = new Set<string>();

  const pushField = (key: string, value: unknown) => {
    if (!isDisplayableScalar(value)) {
      return;
    }

    const stringValue = String(value).trim();
    if (isUrlValue(stringValue)) {
      return;
    }

    const label = prettifyKey(key);
    if (!label || seenLabels.has(label)) {
      return;
    }

    seenLabels.add(label);
    fields.push({ label, value: stringValue });
  };

  for (const key of PRIORITY_CONTEXT_KEYS) {
    if (key in metadata) {
      pushField(key, metadata[key]);
    }
  }

  Object.entries(metadata).forEach(([key, value]) => {
    if (fields.length >= 8) {
      return;
    }
    pushField(key, value);
  });

  return fields;
};
