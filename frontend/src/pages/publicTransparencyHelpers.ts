import type { AppointmentStatus } from "@/types";

export const PUBLIC_APPOINTMENT_STATUS_OPTIONS: Array<{ value: "all" | AppointmentStatus; label: string }> = [
  { value: "all", label: "All statuses" },
  { value: "nominated", label: "Nominated" },
  { value: "under_vetting", label: "Under vetting" },
  { value: "committee_review", label: "Committee review" },
  { value: "confirmation_pending", label: "Confirmation pending" },
  { value: "appointed", label: "Appointed" },
  { value: "rejected", label: "Rejected" },
  { value: "withdrawn", label: "Withdrawn" },
  { value: "serving", label: "Serving" },
  { value: "exited", label: "Exited" },
];

const PUBLIC_APPOINTMENT_STATUS_VALUES = new Set<"all" | AppointmentStatus>(
  PUBLIC_APPOINTMENT_STATUS_OPTIONS.map((option) => option.value),
);

export function formatPublicDate(value: string | null): string {
  if (!value) {
    return "Not specified";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString();
}

export function publicStatusLabel(value: AppointmentStatus): string {
  return value
    .split("_")
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

export function normalizePublishedSearch(value: string | null): string {
  return String(value || "").trim();
}

export function normalizePublishedStatus(value: string | null): "all" | AppointmentStatus {
  const normalized = String(value || "").trim() as "all" | AppointmentStatus;
  if (PUBLIC_APPOINTMENT_STATUS_VALUES.has(normalized)) {
    return normalized;
  }
  return "all";
}

export function buildPublicAppointmentFilterHref(
  basePath: string,
  filters: {
    search?: string | null;
    status?: "all" | AppointmentStatus | null;
    hash?: string | null;
  },
): string {
  const params = new URLSearchParams();
  const normalizedSearch = normalizePublishedSearch(filters.search || "");
  const normalizedStatus = normalizePublishedStatus(filters.status || "all");

  if (normalizedSearch) {
    params.set("search", normalizedSearch);
  }
  if (normalizedStatus !== "all") {
    params.set("status", normalizedStatus);
  }

  const query = params.toString();
  const normalizedHash = String(filters.hash || "").replace(/^#/, "").trim();
  const pathWithQuery = query ? `${basePath}?${query}` : basePath;
  return normalizedHash ? `${pathWithQuery}#${normalizedHash}` : pathWithQuery;
}
