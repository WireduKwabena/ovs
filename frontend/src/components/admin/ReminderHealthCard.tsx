import React, { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, CalendarClock, CheckCircle2, RefreshCw } from "lucide-react";

import { videoCallService } from "@/services/videoCall.service";
import type { VideoMeetingReminderHealth } from "@/types";

const POLL_INTERVAL_MS = 60_000;

export type ReminderHealthStatus = "checking" | "healthy" | "attention" | "unavailable";

interface ReminderHealthCardProps {
  onStatusChange?: (status: ReminderHealthStatus) => void;
}

const deriveStatus = (payload: VideoMeetingReminderHealth): ReminderHealthStatus => {
  const hasFailures =
    payload.soon_retry_pending > 0 ||
    payload.soon_retry_exhausted > 0 ||
    payload.start_now_retry_pending > 0 ||
    payload.start_now_retry_exhausted > 0 ||
    payload.time_up_retry_pending > 0 ||
    payload.time_up_retry_exhausted > 0;
  return hasFailures ? "attention" : "healthy";
};

const badgeClass = (value: number): string =>
  value > 0
    ? "inline-flex rounded-full bg-rose-100 px-2 py-0.5 text-[11px] font-semibold text-rose-700"
    : "inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700";

const ValueRow: React.FC<{ label: string; pending: number; exhausted: number }> = ({ label, pending, exhausted }) => (
  <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
    <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">{label}</p>
    <div className="flex items-center justify-between text-sm">
      <span className="text-slate-800">Retry pending</span>
      <span className={badgeClass(pending)}>{pending}</span>
    </div>
    <div className="flex items-center justify-between text-sm">
      <span className="text-slate-800">Retry exhausted</span>
      <span className={badgeClass(exhausted)}>{exhausted}</span>
    </div>
  </div>
);

const ReminderHealthCard: React.FC<ReminderHealthCardProps> = ({ onStatusChange }) => {
  const [health, setHealth] = useState<VideoMeetingReminderHealth | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastCheckedAt, setLastCheckedAt] = useState<Date | null>(null);
  const latestRef = useRef<VideoMeetingReminderHealth | null>(null);

  const load = useCallback(
    async (mode: "initial" | "refresh" | "poll" = "initial") => {
      if (mode === "initial") {
        setIsLoading(true);
        onStatusChange?.("checking");
      }
      if (mode === "refresh") {
        setIsRefreshing(true);
      }
      if (mode !== "poll") {
        setError(null);
      }

      try {
        const payload = await videoCallService.getReminderHealth();
        setHealth(payload);
        latestRef.current = payload;
        setLastCheckedAt(new Date());
        setError(null);
        onStatusChange?.(deriveStatus(payload));
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to fetch reminder health.";
        setError(message);
        onStatusChange?.(latestRef.current ? deriveStatus(latestRef.current) : "unavailable");
      } finally {
        if (mode === "initial") {
          setIsLoading(false);
        }
        if (mode === "refresh") {
          setIsRefreshing(false);
        }
      }
    },
    [onStatusChange],
  );

  useEffect(() => {
    void load("initial");
  }, [load]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void load("poll");
    }, POLL_INTERVAL_MS);
    return () => {
      window.clearInterval(interval);
    };
  }, [load]);

  const status = health ? deriveStatus(health) : "unavailable";
  const statusLabel =
    status === "healthy"
      ? "Healthy"
      : status === "attention"
        ? "Attention Needed"
        : status === "checking"
          ? "Checking"
          : "Unavailable";
  const statusClass =
    status === "healthy"
      ? "inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700"
      : status === "attention"
        ? "inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700"
        : "inline-flex rounded-full bg-slate-200 px-2 py-0.5 text-[11px] font-semibold text-slate-800";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="inline-flex items-center gap-2 text-lg font-semibold text-slate-900">
              <CalendarClock className="h-5 w-5 text-indigo-600" />
              Reminder Runtime
            </h2>
            <span className={statusClass}>{statusLabel}</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-800">
            {lastCheckedAt ? `Last checked ${lastCheckedAt.toLocaleTimeString()}` : "Not checked yet"}
          </p>
        </div>

        <button
          type="button"
          onClick={() => void load("refresh")}
          disabled={isLoading || isRefreshing}
          className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-900 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
          {isRefreshing ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {isLoading && !health ? (
        <p className="mt-3 text-sm text-slate-800">Checking reminder health...</p>
      ) : (
        <>
          {error ? (
            <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              <div className="inline-flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" />
                {error}
              </div>
            </div>
          ) : null}

          {health ? (
            <div className="mt-4 space-y-3">
              <p className="text-xs text-slate-700">
                Max retries configured: <span className="font-semibold text-slate-900">{health.max_retries}</span>
              </p>
              <div className="grid gap-3 md:grid-cols-3">
                <ValueRow label="Starting Soon" pending={health.soon_retry_pending} exhausted={health.soon_retry_exhausted} />
                <ValueRow
                  label="Start Now"
                  pending={health.start_now_retry_pending}
                  exhausted={health.start_now_retry_exhausted}
                />
                <ValueRow label="Time Up" pending={health.time_up_retry_pending} exhausted={health.time_up_retry_exhausted} />
              </div>

              {status === "healthy" ? (
                <p className="inline-flex items-center gap-2 text-xs text-emerald-700">
                  <CheckCircle2 className="h-4 w-4" />
                  No pending or exhausted reminder retries.
                </p>
              ) : null}
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-800">No reminder health data available.</p>
          )}
        </>
      )}
    </div>
  );
};

export default ReminderHealthCard;
