import React, { useEffect, useMemo, useRef, useState } from "react";
import { LiveKitRoom, RoomAudioRenderer, VideoConference } from "@livekit/components-react";
import {
  CalendarClock,
  CheckCircle2,
  Clock3,
  Download,
  History,
  Loader2,
  PlayCircle,
  RefreshCcw,
  Video,
  XCircle,
} from "lucide-react";
import { toast } from "react-toastify";
import { useSearchParams } from "react-router-dom";

import Modal from "@/components/common/Modal";
import { useAuth } from "@/hooks/useAuth";
import { videoCallService } from "@/services/videoCall.service";
import type { VideoMeeting, VideoMeetingCreatePayload, VideoMeetingEvent, VideoMeetingJoinToken } from "@/types";
import { downloadCsvFile } from "@/utils/csv";

const statusClass: Record<string, string> = {
  scheduled: "bg-blue-100 text-blue-700",
  ongoing: "bg-emerald-100 text-emerald-700",
  completed: "bg-slate-100 text-slate-700",
  cancelled: "bg-rose-100 text-rose-700",
};

const meetingEventActionLabel: Record<string, string> = {
  created: "Created",
  rescheduled: "Rescheduled",
  extended: "Extended",
  cancelled: "Cancelled",
  started: "Started",
  completed: "Completed",
  left: "Left",
};

const meetingEventScopeLabel: Record<string, string> = {
  single: "single",
  future: "future-series",
  all: "all-series",
};

const meetingEventActionClass: Record<string, string> = {
  created: "bg-emerald-100 text-emerald-700 border border-emerald-200",
  rescheduled: "bg-indigo-100 text-indigo-700 border border-indigo-200",
  extended: "bg-blue-100 text-blue-700 border border-blue-200",
  cancelled: "bg-rose-100 text-rose-700 border border-rose-200",
  started: "bg-teal-100 text-teal-700 border border-teal-200",
  completed: "bg-slate-100 text-slate-700 border border-slate-200",
  left: "bg-amber-100 text-amber-700 border border-amber-200",
};

const meetingEventScopeClass: Record<string, string> = {
  single: "bg-slate-100 text-slate-700 border border-slate-200",
  future: "bg-cyan-100 text-cyan-700 border border-cyan-200",
  all: "bg-orange-100 text-orange-700 border border-orange-200",
};

type MeetingTemplate = "custom" | "one_on_one" | "panel_screening" | "final_panel";
type RecurrencePattern = "none" | "daily" | "weekly";
type SeriesScope = "future" | "all";
type SeriesAction = "shift" | "cancel" | "reschedule";
type TimelineFilterMode = "all" | "meeting" | "series";
type TimelineTimeRange = "all" | "24h" | "7d" | "30d";
const SERIES_CANCEL_ALL_PHRASE = "CANCEL ALL";

const TEMPLATE_PRESETS: Record<Exclude<MeetingTemplate, "custom">, {
  title: string;
  description: string;
  durationMinutes: number;
  reminderBeforeMinutes: number;
}> = {
  one_on_one: {
    title: "1v1 Candidate Screening",
    description: "Structured one-on-one vetting interview with candidate.",
    durationMinutes: 45,
    reminderBeforeMinutes: 15,
  },
  panel_screening: {
    title: "Panel Candidate Interview",
    description: "1vMany panel interview for candidate assessment.",
    durationMinutes: 60,
    reminderBeforeMinutes: 20,
  },
  final_panel: {
    title: "Final Panel Review",
    description: "Final stage panel discussion with hiring stakeholders.",
    durationMinutes: 90,
    reminderBeforeMinutes: 30,
  },
};

const fromDatetimeLocal = (value: string): string => {
  const date = new Date(value);
  return date.toISOString();
};

const toDatetimeLocal = (isoValue: string): string => {
  const date = new Date(isoValue);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
};

const toCalendarTimestamp = (isoValue: string): string => {
  const date = new Date(isoValue);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
};

const buildGoogleCalendarUrl = (meeting: VideoMeeting): string => {
  const start = toCalendarTimestamp(meeting.scheduled_start);
  const end = toCalendarTimestamp(meeting.scheduled_end);
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: meeting.title || "Video Meeting",
    dates: `${start}/${end}`,
    details: meeting.description || "Scheduled vetting video interview",
    location: `LiveKit Room: ${meeting.livekit_room_name}`,
    ctz: meeting.timezone || "UTC",
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
};

const triggerFileDownload = (blob: Blob, filename: string): void => {
  const blobUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(blobUrl);
};

const VideoCallsPage: React.FC = () => {
  const { isHrOrAdmin } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [meetings, setMeetings] = useState<VideoMeeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [joiningMeetingId, setJoiningMeetingId] = useState<string | null>(null);
  const [activeJoin, setActiveJoin] = useState<{
    meeting: VideoMeeting;
    credentials: VideoMeetingJoinToken;
  } | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | VideoMeeting["status"]>("all");
  const [actionMeetingId, setActionMeetingId] = useState<string | null>(null);
  const [expandedRescheduleId, setExpandedRescheduleId] = useState<string | null>(null);
  const [expandedEventsId, setExpandedEventsId] = useState<string | null>(null);
  const [reschedulingId, setReschedulingId] = useState<string | null>(null);
  const [loadingEventsId, setLoadingEventsId] = useState<string | null>(null);
  const [downloadingIcsId, setDownloadingIcsId] = useState<string | null>(null);
  const [rescheduleDrafts, setRescheduleDrafts] = useState<
    Record<string, { start: string; end: string; timezone: string }>
  >({});
  const [seriesScopeDrafts, setSeriesScopeDrafts] = useState<Record<string, SeriesScope>>({});
  const [eventTimelineByMeeting, setEventTimelineByMeeting] = useState<Record<string, VideoMeetingEvent[]>>({});
  const [eventFilterByMeeting, setEventFilterByMeeting] = useState<Record<string, TimelineFilterMode>>({});
  const [eventRangeByMeeting, setEventRangeByMeeting] = useState<Record<string, TimelineTimeRange>>({});
  const [seriesConfirmation, setSeriesConfirmation] = useState<{
    meeting: VideoMeeting;
    scope: SeriesScope;
    action: SeriesAction;
  } | null>(null);
  const [seriesConfirmationText, setSeriesConfirmationText] = useState("");
  const meetingRefs = useRef<Record<string, HTMLElement | null>>({});
  const missingFocusNoticeRef = useRef<string | null>(null);
  const autoJoinAttemptedRef = useRef<string | null>(null);
  const focusedMeetingId = searchParams.get("meeting");
  const autojoinValue = (searchParams.get("autojoin") || "").toLowerCase();
  const shouldAutoJoin = autojoinValue === "1" || autojoinValue === "true" || autojoinValue === "yes";

  const [form, setForm] = useState({
    template: "custom" as MeetingTemplate,
    title: "",
    description: "",
    caseId: "",
    participantEmails: "",
    start: "",
    end: "",
    timezone: "UTC",
    recurrence: "none" as RecurrencePattern,
    recurrenceCount: "1",
    reminderBeforeMinutes: "15",
  });

  const sortedMeetings = useMemo(
    () =>
      [...meetings].sort(
        (a, b) => new Date(a.scheduled_start).getTime() - new Date(b.scheduled_start).getTime(),
      ),
    [meetings],
  );
  const filteredMeetings = useMemo(
    () => (statusFilter === "all" ? sortedMeetings : sortedMeetings.filter((meeting) => meeting.status === statusFilter)),
    [sortedMeetings, statusFilter],
  );

  const loadMeetings = async () => {
    setLoading(true);
    try {
      const payload = await videoCallService.list();
      setMeetings(payload);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load meetings.";
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadMeetings();
  }, []);

  const applyDurationFromStart = (durationMinutes: number) => {
    if (!form.start) {
      toast.info("Choose a meeting start time first.");
      return;
    }
    const startDate = new Date(fromDatetimeLocal(form.start));
    const endDate = new Date(startDate.getTime() + durationMinutes * 60_000);
    setForm((current) => ({ ...current, end: toDatetimeLocal(endDate.toISOString()) }));
  };

  const applyTemplatePreset = (template: MeetingTemplate) => {
    if (template === "custom") {
      setForm((current) => ({ ...current, template }));
      return;
    }

    const preset = TEMPLATE_PRESETS[template];
    setForm((current) => {
      const next = {
        ...current,
        template,
        title: preset.title,
        description: preset.description,
        reminderBeforeMinutes: String(preset.reminderBeforeMinutes),
      };

      if (current.start) {
        const startDate = new Date(fromDatetimeLocal(current.start));
        const endDate = new Date(startDate.getTime() + preset.durationMinutes * 60_000);
        next.end = toDatetimeLocal(endDate.toISOString());
      }
      return next;
    });
  };

  useEffect(() => {
    if (!focusedMeetingId) {
      missingFocusNoticeRef.current = null;
      autoJoinAttemptedRef.current = null;
      return;
    }
    if (statusFilter !== "all") {
      setStatusFilter("all");
    }
    if (loading) {
      return;
    }
    const exists = meetings.some((meeting) => meeting.id === focusedMeetingId);
    if (!exists) {
      if (missingFocusNoticeRef.current !== focusedMeetingId) {
        toast.info("The requested meeting is no longer available.");
        missingFocusNoticeRef.current = focusedMeetingId;
      }
      return;
    }
    const node = meetingRefs.current[focusedMeetingId];
    if (node) {
      node.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [focusedMeetingId, loading, meetings, statusFilter]);

  const handleCreate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isHrOrAdmin) {
      return;
    }

    setSubmitting(true);
    try {
      const participant_emails = form.participantEmails
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      const baseStart = new Date(fromDatetimeLocal(form.start));
      const baseEnd = new Date(fromDatetimeLocal(form.end));
      if (Number.isNaN(baseStart.getTime()) || Number.isNaN(baseEnd.getTime())) {
        toast.error("Invalid start or end datetime.");
        return;
      }
      if (baseEnd <= baseStart) {
        toast.error("End time must be after start time.");
        return;
      }

      const reminderBeforeMinutes = Number(form.reminderBeforeMinutes);
      if (!Number.isFinite(reminderBeforeMinutes) || reminderBeforeMinutes < 1 || reminderBeforeMinutes > 120) {
        toast.error("Reminder lead-time must be between 1 and 120 minutes.");
        return;
      }

      const recurrenceCountRaw = Number(form.recurrenceCount || "1");
      const recurrenceCount = form.recurrence === "none" ? 1 : Math.min(12, Math.max(1, Math.trunc(recurrenceCountRaw || 1)));
      const payload: VideoMeetingCreatePayload = {
        title: form.title.trim(),
        description: form.description.trim(),
        scheduled_start: baseStart.toISOString(),
        scheduled_end: baseEnd.toISOString(),
        timezone: form.timezone || "UTC",
        reminder_before_minutes: reminderBeforeMinutes,
      };

      if (form.caseId.trim()) {
        payload.case = form.caseId.trim();
      }
      if (participant_emails.length > 0) {
        payload.participant_emails = participant_emails;
      }

      let createdCount = 0;
      if (form.recurrence === "none") {
        await videoCallService.create(payload);
        createdCount = 1;
      } else {
        const response = await videoCallService.scheduleSeries({
          ...payload,
          recurrence: form.recurrence,
          occurrences: recurrenceCount,
        });
        createdCount = response.count;
      }

      toast.success(createdCount === 1 ? "Video call scheduled." : `${createdCount} video calls scheduled.`);
      setForm((current) => ({
        ...current,
        title: current.recurrence === "none" ? "" : current.title,
        description: current.recurrence === "none" ? "" : current.description,
        caseId: "",
        participantEmails: "",
        recurrence: "none",
        recurrenceCount: "1",
      }));
      await loadMeetings();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to schedule meeting.";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleJoin = React.useCallback(async (meeting: VideoMeeting) => {
    setJoiningMeetingId(meeting.id);
    try {
      const credentials = await videoCallService.getJoinToken(meeting.id);
      setActiveJoin({ meeting, credentials });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to join meeting.";
      toast.error(message);
    } finally {
      setJoiningMeetingId(null);
    }
  }, []);

  useEffect(() => {
    if (!focusedMeetingId || !shouldAutoJoin || loading || activeJoin || joiningMeetingId) {
      return;
    }
    if (autoJoinAttemptedRef.current === focusedMeetingId) {
      return;
    }
    const targetMeeting = meetings.find((meeting) => meeting.id === focusedMeetingId);
    if (!targetMeeting) {
      return;
    }
    if (targetMeeting.status === "cancelled" || targetMeeting.status === "completed") {
      return;
    }

    autoJoinAttemptedRef.current = focusedMeetingId;
    void handleJoin(targetMeeting);

    const next = new URLSearchParams(searchParams);
    next.delete("autojoin");
    setSearchParams(next, { replace: true });
  }, [
    activeJoin,
    focusedMeetingId,
    handleJoin,
    joiningMeetingId,
    loading,
    meetings,
    searchParams,
    setSearchParams,
    shouldAutoJoin,
  ]);

  const handleCloseRoom = async () => {
    if (!activeJoin) {
      return;
    }
    try {
      await videoCallService.leave(activeJoin.meeting.id);
    } catch {
      // no-op
    }
    setActiveJoin(null);
  };

  const handleDownloadIcs = async (meeting: VideoMeeting) => {
    setDownloadingIcsId(meeting.id);
    try {
      const blob = await videoCallService.downloadCalendarIcs(meeting.id);
      const safeTitle = (meeting.title || "video-meeting").replace(/[^a-zA-Z0-9-_]/g, "_");
      triggerFileDownload(blob, `${safeTitle}-${meeting.id}.ics`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to download meeting calendar file.";
      toast.error(message);
    } finally {
      setDownloadingIcsId(null);
    }
  };

  const handleQuickExtend = async (meeting: VideoMeeting) => {
    setActionMeetingId(meeting.id);
    try {
      await videoCallService.extend(meeting.id, 15);
      toast.success("Meeting extended by 15 minutes.");
      await loadMeetings();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to extend meeting.";
      toast.error(message);
    } finally {
      setActionMeetingId(null);
    }
  };

  const handleQuickShift = async (meeting: VideoMeeting) => {
    setActionMeetingId(meeting.id);
    try {
      const shiftedStart = new Date(new Date(meeting.scheduled_start).getTime() + 30 * 60_000);
      const shiftedEnd = new Date(new Date(meeting.scheduled_end).getTime() + 30 * 60_000);
      await videoCallService.reschedule(meeting.id, {
        scheduled_start: shiftedStart.toISOString(),
        scheduled_end: shiftedEnd.toISOString(),
        timezone: meeting.timezone,
      });
      toast.success("Meeting moved by 30 minutes.");
      await loadMeetings();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to reschedule meeting.";
      toast.error(message);
    } finally {
      setActionMeetingId(null);
    }
  };

  const handleCancelMeeting = async (meeting: VideoMeeting) => {
    setActionMeetingId(meeting.id);
    try {
      await videoCallService.cancel(meeting.id, "Cancelled by organizer.");
      toast.info("Meeting cancelled.");
      await loadMeetings();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to cancel meeting.";
      toast.error(message);
    } finally {
      setActionMeetingId(null);
    }
  };

  const handleStartMeeting = async (meeting: VideoMeeting) => {
    setActionMeetingId(meeting.id);
    try {
      await videoCallService.start(meeting.id);
      toast.success("Meeting started.");
      await loadMeetings();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to start meeting.";
      toast.error(message);
    } finally {
      setActionMeetingId(null);
    }
  };

  const handleCompleteMeeting = async (meeting: VideoMeeting) => {
    setActionMeetingId(meeting.id);
    try {
      await videoCallService.complete(meeting.id);
      toast.success("Meeting marked completed.");
      await loadMeetings();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to complete meeting.";
      toast.error(message);
    } finally {
      setActionMeetingId(null);
    }
  };

  const toggleReschedulePanel = (meeting: VideoMeeting) => {
    setRescheduleDrafts((current) => ({
      ...current,
      [meeting.id]: current[meeting.id] || {
        start: toDatetimeLocal(meeting.scheduled_start),
        end: toDatetimeLocal(meeting.scheduled_end),
        timezone: meeting.timezone || "UTC",
      },
    }));
    setExpandedRescheduleId((current) => (current === meeting.id ? null : meeting.id));
  };

  const updateRescheduleDraft = (meetingId: string, field: "start" | "end" | "timezone", value: string) => {
    setRescheduleDrafts((current) => ({
      ...current,
      [meetingId]: {
        start: current[meetingId]?.start || "",
        end: current[meetingId]?.end || "",
        timezone: current[meetingId]?.timezone || "UTC",
        [field]: value,
      },
    }));
  };

  const submitReschedule = async (meeting: VideoMeeting) => {
    const draft = rescheduleDrafts[meeting.id];
    if (!draft?.start || !draft?.end) {
      toast.error("Provide both start and end time.");
      return;
    }
    setReschedulingId(meeting.id);
    try {
      await videoCallService.reschedule(meeting.id, {
        scheduled_start: fromDatetimeLocal(draft.start),
        scheduled_end: fromDatetimeLocal(draft.end),
        timezone: draft.timezone || "UTC",
      });
      toast.success("Meeting rescheduled.");
      setExpandedRescheduleId(null);
      await loadMeetings();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to reschedule meeting.";
      toast.error(message);
    } finally {
      setReschedulingId(null);
    }
  };

  const getTimelineFilterMode = (meeting: VideoMeeting): TimelineFilterMode => {
    const saved = eventFilterByMeeting[meeting.id];
    if (saved) {
      return saved;
    }
    return meeting.series_id ? "all" : "meeting";
  };

  const getTimelineTimeRange = (meeting: VideoMeeting): TimelineTimeRange => {
    const saved = eventRangeByMeeting[meeting.id];
    if (saved) {
      return saved;
    }
    return "all";
  };

  const getVisibleTimelineEvents = (meeting: VideoMeeting): VideoMeetingEvent[] => {
    const events = eventTimelineByMeeting[meeting.id] || [];
    const mode = getTimelineFilterMode(meeting);
    const range = getTimelineTimeRange(meeting);
    const nowMs = Date.now();
    const rangeWindowMs =
      range === "24h"
        ? 24 * 60 * 60 * 1000
        : range === "7d"
          ? 7 * 24 * 60 * 60 * 1000
          : range === "30d"
            ? 30 * 24 * 60 * 60 * 1000
            : null;

    let scopedEvents: VideoMeetingEvent[] = events;
    if (mode === "meeting") {
      scopedEvents = events.filter((event) => event.meeting === meeting.id);
    } else if (mode === "series") {
      scopedEvents = events.filter((event) => event.meeting !== meeting.id);
    }

    if (rangeWindowMs === null) {
      return scopedEvents;
    }

    return scopedEvents.filter((event) => {
      const eventTimeMs = new Date(event.created_at).getTime();
      return Number.isFinite(eventTimeMs) && nowMs - eventTimeMs <= rangeWindowMs;
    });
  };

  const loadMeetingEvents = async (meeting: VideoMeeting, mode?: TimelineFilterMode) => {
    const filterMode = mode || getTimelineFilterMode(meeting);
    const includeSeries = Boolean(meeting.series_id) && filterMode !== "meeting";
    setLoadingEventsId(meeting.id);
    try {
      const events = await videoCallService.listEvents(meeting.id, {
        includeSeries,
        limit: 100,
      });
      setEventTimelineByMeeting((current) => ({
        ...current,
        [meeting.id]: events,
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load meeting history.";
      toast.error(message);
    } finally {
      setLoadingEventsId(null);
    }
  };

  const updateTimelineFilterMode = async (meeting: VideoMeeting, mode: TimelineFilterMode) => {
    setEventFilterByMeeting((current) => ({
      ...current,
      [meeting.id]: mode,
    }));
    await loadMeetingEvents(meeting, mode);
  };

  const updateTimelineTimeRange = (meeting: VideoMeeting, range: TimelineTimeRange) => {
    setEventRangeByMeeting((current) => ({
      ...current,
      [meeting.id]: range,
    }));
  };

  const exportTimelineCsv = (meeting: VideoMeeting) => {
    const visibleEvents = getVisibleTimelineEvents(meeting);
    if (visibleEvents.length === 0) {
      toast.info("No timeline rows to export.");
      return;
    }

    const header = [
      "timestamp",
      "action",
      "scope",
      "meeting_id",
      "actor_name",
      "actor_email",
      "detail",
    ];
    const rows = visibleEvents.map((event) => [
      new Date(event.created_at).toISOString(),
      meetingEventActionLabel[event.action] || event.action,
      meetingEventScopeLabel[event.scope] || event.scope,
      event.meeting,
      event.actor_name,
      event.actor_email || "",
      event.detail || "",
    ]);

    const safeTitle = (meeting.title || "meeting").replace(/[^a-zA-Z0-9-_]/g, "_");
    const filename = `${safeTitle}-${meeting.id}-history-${getTimelineFilterMode(meeting)}-${getTimelineTimeRange(meeting)}.csv`;
    downloadCsvFile(header, rows, filename);
  };

  const toggleEventsPanel = async (meeting: VideoMeeting) => {
    if (expandedEventsId === meeting.id) {
      setExpandedEventsId(null);
      return;
    }
    setExpandedEventsId(meeting.id);
    if (!eventTimelineByMeeting[meeting.id]) {
      await loadMeetingEvents(meeting, getTimelineFilterMode(meeting));
    }
  };

  const getSeriesScope = (meetingId: string): SeriesScope => seriesScopeDrafts[meetingId] || "future";

  const updateSeriesScope = (meetingId: string, scope: SeriesScope) => {
    setSeriesScopeDrafts((current) => ({
      ...current,
      [meetingId]: scope,
    }));
  };

  const handleQuickShiftSeries = async (meeting: VideoMeeting) => {
    if (!meeting.series_id) {
      return;
    }
    setActionMeetingId(meeting.id);
    try {
      const shiftedStart = new Date(new Date(meeting.scheduled_start).getTime() + 30 * 60_000);
      const shiftedEnd = new Date(new Date(meeting.scheduled_end).getTime() + 30 * 60_000);
      const response = await videoCallService.rescheduleSeries(meeting.id, {
        scheduled_start: shiftedStart.toISOString(),
        scheduled_end: shiftedEnd.toISOString(),
        timezone: meeting.timezone,
        scope: getSeriesScope(meeting.id),
      });
      toast.success(`${response.count} series meeting(s) moved by 30 minutes.`);
      await loadMeetings();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to reschedule meeting series.";
      toast.error(message);
    } finally {
      setActionMeetingId(null);
    }
  };

  const handleCancelSeries = async (meeting: VideoMeeting) => {
    if (!meeting.series_id) {
      return;
    }
    setActionMeetingId(meeting.id);
    try {
      const response = await videoCallService.cancelSeries(meeting.id, {
        reason: "Cancelled by organizer.",
        scope: getSeriesScope(meeting.id),
      });
      toast.info(`${response.count} series meeting(s) cancelled.`);
      await loadMeetings();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to cancel meeting series.";
      toast.error(message);
    } finally {
      setActionMeetingId(null);
    }
  };

  const submitSeriesRescheduleDirect = async (meeting: VideoMeeting) => {
    if (!meeting.series_id) {
      return;
    }
    const draft = rescheduleDrafts[meeting.id];
    if (!draft?.start || !draft?.end) {
      toast.error("Provide both start and end time.");
      return;
    }
    setReschedulingId(meeting.id);
    try {
      const response = await videoCallService.rescheduleSeries(meeting.id, {
        scheduled_start: fromDatetimeLocal(draft.start),
        scheduled_end: fromDatetimeLocal(draft.end),
        timezone: draft.timezone || "UTC",
        scope: getSeriesScope(meeting.id),
      });
      toast.success(`${response.count} series meeting(s) rescheduled.`);
      setExpandedRescheduleId(null);
      await loadMeetings();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to reschedule meeting series.";
      toast.error(message);
    } finally {
      setReschedulingId(null);
    }
  };

  const requestSeriesActionConfirmation = (meeting: VideoMeeting, action: SeriesAction) => {
    if (!meeting.series_id) {
      return;
    }
    setSeriesConfirmationText("");
    setSeriesConfirmation({
      meeting,
      action,
      scope: getSeriesScope(meeting.id),
    });
  };

  const submitSeriesReschedule = async (meeting: VideoMeeting) => {
    if (!meeting.series_id) {
      return;
    }
    const draft = rescheduleDrafts[meeting.id];
    if (!draft?.start || !draft?.end) {
      toast.error("Provide both start and end time.");
      return;
    }
    requestSeriesActionConfirmation(meeting, "reschedule");
  };

  const confirmSeriesAction = async () => {
    if (!seriesConfirmation) {
      return;
    }
    const requiresTypedConfirmation =
      seriesConfirmation.action === "cancel" && seriesConfirmation.scope === "all";
    const isTypedConfirmationValid =
      seriesConfirmationText.trim().toUpperCase() === SERIES_CANCEL_ALL_PHRASE;
    if (requiresTypedConfirmation && !isTypedConfirmationValid) {
      toast.error(`Type "${SERIES_CANCEL_ALL_PHRASE}" to confirm cancelling all series meetings.`);
      return;
    }

    const { action, meeting } = seriesConfirmation;
    setSeriesConfirmation(null);
    setSeriesConfirmationText("");

    if (action === "shift") {
      await handleQuickShiftSeries(meeting);
      return;
    }
    if (action === "cancel") {
      await handleCancelSeries(meeting);
      return;
    }
    await submitSeriesRescheduleDirect(meeting);
  };

  const requiresTypedSeriesConfirmation =
    seriesConfirmation?.action === "cancel" && seriesConfirmation?.scope === "all";
  const isSeriesConfirmationReady =
    !requiresTypedSeriesConfirmation ||
    seriesConfirmationText.trim().toUpperCase() === SERIES_CANCEL_ALL_PHRASE;

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold text-slate-900">Video Calls</h1>
              <p className="mt-1 text-sm text-slate-600">
                Schedule and run 1v1 or 1vMany candidate meetings through LiveKit.
              </p>
            </div>
            <button
              type="button"
              onClick={() => void loadMeetings()}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
            >
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </button>
          </div>
        </div>

        {isHrOrAdmin && (
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">Schedule a meeting</h2>
            <form className="mt-4 grid gap-4 md:grid-cols-2" onSubmit={handleCreate}>
              <label className="space-y-1 text-sm text-slate-700">
                <span>Template</span>
                <select
                  value={form.template}
                  onChange={(event) => applyTemplatePreset(event.target.value as MeetingTemplate)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                >
                  <option value="custom">Custom</option>
                  <option value="one_on_one">1v1 Screening</option>
                  <option value="panel_screening">Panel Screening (1vMany)</option>
                  <option value="final_panel">Final Panel (1vMany)</option>
                </select>
              </label>

              <label className="space-y-1 text-sm text-slate-700">
                <span>Reminder lead-time (minutes)</span>
                <input
                  type="number"
                  min={1}
                  max={120}
                  value={form.reminderBeforeMinutes}
                  onChange={(event) => setForm((prev) => ({ ...prev, reminderBeforeMinutes: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                />
              </label>

              <label className="space-y-1 text-sm text-slate-700">
                <span>Title</span>
                <input
                  required
                  value={form.title}
                  onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                />
              </label>

              <label className="space-y-1 text-sm text-slate-700">
                <span>Case ID (optional but recommended)</span>
                <input
                  value={form.caseId}
                  onChange={(event) => setForm((prev) => ({ ...prev, caseId: event.target.value }))}
                  placeholder="UUID case id"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                />
              </label>

              <label className="space-y-1 text-sm text-slate-700 md:col-span-2">
                <span>Description</span>
                <textarea
                  value={form.description}
                  onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
                  className="min-h-24 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                />
              </label>

              <label className="space-y-1 text-sm text-slate-700">
                <span>Start</span>
                <input
                  required
                  type="datetime-local"
                  value={form.start}
                  onChange={(event) => setForm((prev) => ({ ...prev, start: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                />
              </label>

              <label className="space-y-1 text-sm text-slate-700">
                <span>End</span>
                <input
                  required
                  type="datetime-local"
                  value={form.end}
                  onChange={(event) => setForm((prev) => ({ ...prev, end: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                />
              </label>

              <div className="space-y-1 text-sm text-slate-700">
                <span>Quick duration presets</span>
                <div className="flex flex-wrap gap-2">
                  {[30, 45, 60, 90].map((minutes) => (
                    <button
                      key={minutes}
                      type="button"
                      onClick={() => applyDurationFromStart(minutes)}
                      className="rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
                    >
                      {minutes} min
                    </button>
                  ))}
                </div>
              </div>

              <label className="space-y-1 text-sm text-slate-700">
                <span>Recurrence</span>
                <select
                  value={form.recurrence}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      recurrence: event.target.value as RecurrencePattern,
                      recurrenceCount: event.target.value === "none" ? "1" : prev.recurrenceCount,
                    }))
                  }
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                >
                  <option value="none">No recurrence</option>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                </select>
              </label>

              {form.recurrence !== "none" && (
                <label className="space-y-1 text-sm text-slate-700">
                  <span>Occurrences</span>
                  <input
                    type="number"
                    min={1}
                    max={12}
                    value={form.recurrenceCount}
                    onChange={(event) => setForm((prev) => ({ ...prev, recurrenceCount: event.target.value }))}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                  />
                </label>
              )}

              <label className="space-y-1 text-sm text-slate-700">
                <span>Timezone</span>
                <input
                  value={form.timezone}
                  onChange={(event) => setForm((prev) => ({ ...prev, timezone: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                />
              </label>

              <label className="space-y-1 text-sm text-slate-700">
                <span>Extra participant emails (comma-separated)</span>
                <input
                  value={form.participantEmails}
                  onChange={(event) => setForm((prev) => ({ ...prev, participantEmails: event.target.value }))}
                  placeholder="candidate1@example.com,candidate2@example.com"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                />
              </label>

              <div className="md:col-span-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarClock className="h-4 w-4" />}
                  {submitting ? "Scheduling..." : "Schedule Meeting"}
                </button>
              </div>
            </form>
          </section>
        )}

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-slate-900">Meetings</h2>
            <div className="flex flex-wrap items-center gap-2">
              <label className="inline-flex items-center gap-2 text-xs text-slate-600">
                <Clock3 className="h-3.5 w-3.5" />
                Status
                <select
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value as "all" | VideoMeeting["status"])}
                  className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700"
                >
                  <option value="all">All</option>
                  <option value="scheduled">Scheduled</option>
                  <option value="ongoing">Ongoing</option>
                  <option value="completed">Completed</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </label>
              {focusedMeetingId && (
                <button
                  type="button"
                  onClick={() => setSearchParams({})}
                  className="rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
                >
                  Clear focus
                </button>
              )}
            </div>
          </div>
          {loading ? (
            <div className="mt-4 flex items-center gap-2 text-slate-600">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading meetings...
            </div>
          ) : filteredMeetings.length === 0 ? (
            <p className="mt-4 text-sm text-slate-600">No meetings scheduled yet.</p>
          ) : (
            <div className="mt-4 space-y-3">
              {filteredMeetings.map((meeting) => (
                <article
                  key={meeting.id}
                  ref={(node) => {
                    meetingRefs.current[meeting.id] = node;
                  }}
                  className={`rounded-xl border bg-slate-50 p-4 ${
                    focusedMeetingId === meeting.id
                      ? "border-indigo-400 ring-2 ring-indigo-100"
                      : "border-slate-200"
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <h3 className="text-base font-semibold text-slate-900">{meeting.title}</h3>
                      <p className="text-sm text-slate-700">{meeting.description || "No description provided."}</p>
                      <p className="text-xs text-slate-600">
                        {new Date(meeting.scheduled_start).toLocaleString()} -{" "}
                        {new Date(meeting.scheduled_end).toLocaleString()} ({meeting.timezone})
                      </p>
                      <p className="text-xs text-slate-500">
                        Room: <span className="font-mono">{meeting.livekit_room_name}</span>
                      </p>
                      <p className="text-xs text-slate-500">
                        Reminder: {meeting.reminder_before_minutes} minute(s) before start
                      </p>
                      {meeting.series_id && (
                        <p className="text-xs text-slate-500">
                          Series ID: <span className="font-mono">{meeting.series_id}</span>
                        </p>
                      )}
                      <div className="mt-2 flex flex-wrap gap-2">
                        {meeting.participants.map((participant) => (
                          <span
                            key={participant.id}
                            className="rounded-full border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
                          >
                            {participant.user_full_name} ({participant.role})
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-1 text-xs font-medium ${statusClass[meeting.status] || "bg-slate-100 text-slate-700"}`}
                      >
                        {meeting.status}
                      </span>
                      <button
                        type="button"
                        onClick={() => void handleJoin(meeting)}
                        disabled={joiningMeetingId === meeting.id || meeting.status === "cancelled" || meeting.status === "completed"}
                        className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
                      >
                        <Video className="h-3.5 w-3.5" />
                        {joiningMeetingId === meeting.id ? "Joining..." : "Join"}
                      </button>
                      <a
                        href={buildGoogleCalendarUrl(meeting)}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"
                      >
                        Google Calendar
                      </a>
                      <button
                        type="button"
                        onClick={() => void handleDownloadIcs(meeting)}
                        disabled={downloadingIcsId === meeting.id}
                        className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"
                      >
                        {downloadingIcsId === meeting.id ? "Downloading..." : "Download .ics"}
                      </button>
                      <button
                        type="button"
                        onClick={() => void toggleEventsPanel(meeting)}
                        disabled={loadingEventsId === meeting.id}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60"
                      >
                        {loadingEventsId === meeting.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <History className="h-3.5 w-3.5" />}
                        History
                      </button>
                      {isHrOrAdmin && meeting.series_id && (
                        <label className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700">
                          <span>Series</span>
                          <select
                            value={getSeriesScope(meeting.id)}
                            onChange={(event) => updateSeriesScope(meeting.id, event.target.value as SeriesScope)}
                            className="bg-transparent text-xs text-slate-700 focus:outline-none"
                          >
                            <option value="future">Future</option>
                            <option value="all">All</option>
                          </select>
                        </label>
                      )}
                      {isHrOrAdmin && meeting.status === "scheduled" && (
                        <>
                          <button
                            type="button"
                            onClick={() => void handleStartMeeting(meeting)}
                            disabled={actionMeetingId === meeting.id}
                            className="inline-flex items-center gap-1 rounded-lg border border-emerald-300 px-3 py-2 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-60"
                          >
                            <PlayCircle className="h-3.5 w-3.5" />
                            Start
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleQuickExtend(meeting)}
                            disabled={actionMeetingId === meeting.id}
                            className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"
                          >
                            +15 min
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleQuickShift(meeting)}
                            disabled={actionMeetingId === meeting.id}
                            className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"
                          >
                            Shift +30 min
                          </button>
                          {meeting.series_id && (
                            <button
                              type="button"
                              onClick={() => requestSeriesActionConfirmation(meeting, "shift")}
                              disabled={actionMeetingId === meeting.id}
                              className="rounded-lg border border-indigo-300 px-3 py-2 text-xs font-medium text-indigo-700 hover:bg-indigo-50"
                            >
                              Shift series +30
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => toggleReschedulePanel(meeting)}
                            disabled={actionMeetingId === meeting.id}
                            className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"
                          >
                            Custom time
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleCancelMeeting(meeting)}
                            disabled={actionMeetingId === meeting.id}
                            className="inline-flex items-center gap-1 rounded-lg border border-rose-300 px-3 py-2 text-xs font-medium text-rose-700 hover:bg-rose-50"
                          >
                            <XCircle className="h-3.5 w-3.5" />
                            Cancel
                          </button>
                          {meeting.series_id && (
                            <button
                              type="button"
                              onClick={() => requestSeriesActionConfirmation(meeting, "cancel")}
                              disabled={actionMeetingId === meeting.id}
                              className="inline-flex items-center gap-1 rounded-lg border border-rose-300 px-3 py-2 text-xs font-medium text-rose-700 hover:bg-rose-50"
                            >
                              <XCircle className="h-3.5 w-3.5" />
                              Cancel series
                            </button>
                          )}
                        </>
                      )}
                      {isHrOrAdmin && meeting.status === "ongoing" && (
                        <>
                          <button
                            type="button"
                            onClick={() => void handleQuickExtend(meeting)}
                            disabled={actionMeetingId === meeting.id}
                            className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"
                          >
                            +15 min
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleCompleteMeeting(meeting)}
                            disabled={actionMeetingId === meeting.id}
                            className="inline-flex items-center gap-1 rounded-lg border border-indigo-300 px-3 py-2 text-xs font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-60"
                          >
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            Complete
                          </button>
                          {meeting.series_id && (
                            <button
                              type="button"
                              onClick={() => requestSeriesActionConfirmation(meeting, "cancel")}
                              disabled={actionMeetingId === meeting.id}
                              className="inline-flex items-center gap-1 rounded-lg border border-rose-300 px-3 py-2 text-xs font-medium text-rose-700 hover:bg-rose-50"
                            >
                              <XCircle className="h-3.5 w-3.5" />
                              Cancel series
                            </button>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                  {isHrOrAdmin && expandedRescheduleId === meeting.id && (
                    <div className="mt-3 grid gap-3 rounded-lg border border-slate-200 bg-white p-3 md:grid-cols-3">
                      <label className="space-y-1 text-xs text-slate-700">
                        <span>Start</span>
                        <input
                          type="datetime-local"
                          value={rescheduleDrafts[meeting.id]?.start || ""}
                          onChange={(event) => updateRescheduleDraft(meeting.id, "start", event.target.value)}
                          className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                        />
                      </label>
                      <label className="space-y-1 text-xs text-slate-700">
                        <span>End</span>
                        <input
                          type="datetime-local"
                          value={rescheduleDrafts[meeting.id]?.end || ""}
                          onChange={(event) => updateRescheduleDraft(meeting.id, "end", event.target.value)}
                          className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                        />
                      </label>
                      <label className="space-y-1 text-xs text-slate-700">
                        <span>Timezone</span>
                        <input
                          value={rescheduleDrafts[meeting.id]?.timezone || "UTC"}
                          onChange={(event) => updateRescheduleDraft(meeting.id, "timezone", event.target.value)}
                          className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                        />
                      </label>
                      <div className="md:col-span-3 flex flex-wrap justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setExpandedRescheduleId(null)}
                          className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
                        >
                          Close
                        </button>
                        <button
                          type="button"
                          disabled={reschedulingId === meeting.id}
                          onClick={() => void submitReschedule(meeting)}
                          className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
                        >
                          {reschedulingId === meeting.id ? "Saving..." : "Save schedule"}
                        </button>
                        {meeting.series_id && (
                          <button
                            type="button"
                            disabled={reschedulingId === meeting.id}
                            onClick={() => void submitSeriesReschedule(meeting)}
                            className="rounded-md bg-indigo-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-800 disabled:opacity-60"
                          >
                            {reschedulingId === meeting.id
                              ? "Saving..."
                              : `Save ${getSeriesScope(meeting.id)} series`}
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                  {expandedEventsId === meeting.id && (
                    <div className="mt-3 rounded-lg border border-slate-200 bg-white p-3">
                      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                          Meeting History
                        </h4>
                        <div className="flex flex-wrap items-center gap-2">
                          <label className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700">
                            <span>View</span>
                            <select
                              value={getTimelineFilterMode(meeting)}
                              onChange={(event) => void updateTimelineFilterMode(meeting, event.target.value as TimelineFilterMode)}
                              className="bg-transparent text-xs text-slate-700 focus:outline-none"
                            >
                              <option value="all">All history</option>
                              <option value="meeting">This meeting</option>
                              {meeting.series_id && <option value="series">Other occurrences</option>}
                            </select>
                          </label>
                          <label className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700">
                            <span>Range</span>
                            <select
                              value={getTimelineTimeRange(meeting)}
                              onChange={(event) => updateTimelineTimeRange(meeting, event.target.value as TimelineTimeRange)}
                              className="bg-transparent text-xs text-slate-700 focus:outline-none"
                            >
                              <option value="all">All</option>
                              <option value="24h">Last 24h</option>
                              <option value="7d">Last 7d</option>
                              <option value="30d">Last 30d</option>
                            </select>
                          </label>
                          <button
                            type="button"
                            onClick={() => exportTimelineCsv(meeting)}
                            className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
                          >
                            <Download className="h-3.5 w-3.5" />
                            CSV
                          </button>
                          <button
                            type="button"
                            onClick={() => void loadMeetingEvents(meeting, getTimelineFilterMode(meeting))}
                            disabled={loadingEventsId === meeting.id}
                            className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60"
                          >
                            {loadingEventsId === meeting.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCcw className="h-3.5 w-3.5" />}
                            Refresh
                          </button>
                        </div>
                      </div>
                      <p className="mb-2 text-[11px] text-slate-500">
                        Showing {getVisibleTimelineEvents(meeting).length} event(s)
                      </p>
                      {loadingEventsId === meeting.id && !eventTimelineByMeeting[meeting.id] ? (
                        <p className="text-xs text-slate-600">Loading history...</p>
                      ) : getVisibleTimelineEvents(meeting).length === 0 ? (
                        <p className="text-xs text-slate-600">No history for the selected view.</p>
                      ) : (
                        <div className="space-y-2">
                          {getVisibleTimelineEvents(meeting).map((event) => (
                            <div
                              key={event.id}
                              className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-2"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <span
                                    className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${meetingEventActionClass[event.action] || "bg-slate-100 text-slate-700 border border-slate-200"}`}
                                  >
                                    {meetingEventActionLabel[event.action] || event.action}
                                  </span>
                                  <span
                                    className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${meetingEventScopeClass[event.scope] || "bg-slate-100 text-slate-700 border border-slate-200"}`}
                                  >
                                    {meetingEventScopeLabel[event.scope] || event.scope}
                                  </span>
                                  {event.meeting !== meeting.id && (
                                    <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 font-mono text-[10px] text-slate-600">
                                      occurrence {event.meeting.slice(0, 8)}
                                    </span>
                                  )}
                                </div>
                                <p className="text-[11px] text-slate-500">
                                  {new Date(event.created_at).toLocaleString()}
                                </p>
                              </div>
                              <p className="mt-1 text-xs text-slate-700">
                                {event.detail || "No additional detail."}
                              </p>
                              <p className="mt-1 text-[11px] text-slate-500">
                                By {event.actor_name}
                                {event.actor_email ? ` (${event.actor_email})` : ""}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>

        <Modal
          open={Boolean(seriesConfirmation)}
          title={
            seriesConfirmation?.action === "cancel"
              ? "Cancel series meetings?"
              : seriesConfirmation?.action === "shift"
                ? "Shift series schedule?"
                : "Reschedule series meetings?"
          }
          cancelLabel="Go back"
          confirmLabel={seriesConfirmation?.action === "cancel" ? "Confirm cancel" : "Confirm update"}
          confirmDisabled={!isSeriesConfirmationReady}
          onCancel={() => {
            setSeriesConfirmation(null);
            setSeriesConfirmationText("");
          }}
          onConfirm={() => {
            void confirmSeriesAction();
          }}
        >
          <p className="text-sm text-slate-700">
            {seriesConfirmation
              ? `${seriesConfirmation.action === "cancel"
                  ? "This will cancel"
                  : "This will update"} ${seriesConfirmation.scope === "all" ? "all occurrences in the series" : "the selected meeting and future occurrences"} for "${seriesConfirmation.meeting.title}".`
              : ""}
          </p>
          {seriesConfirmation?.scope === "all" && (
            <p className="mt-2 text-xs text-rose-700">
              Scope is set to &quot;All&quot;. This affects the entire recurring series.
            </p>
          )}
          {requiresTypedSeriesConfirmation && (
            <div className="mt-3 space-y-1">
              <p className="text-xs text-slate-700">
                Type <span className="font-semibold">{SERIES_CANCEL_ALL_PHRASE}</span> to continue.
              </p>
              <input
                value={seriesConfirmationText}
                onChange={(event) => setSeriesConfirmationText(event.target.value)}
                placeholder={SERIES_CANCEL_ALL_PHRASE}
                className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
            </div>
          )}
        </Modal>

        {activeJoin && (
          <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-slate-900">
                  In Call: {activeJoin.meeting.title}
                </h3>
                <p className="text-xs text-slate-600">Room: {activeJoin.credentials.room_name}</p>
              </div>
              <button
                type="button"
                onClick={() => void handleCloseRoom()}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
              >
                Leave Room
              </button>
            </div>
            <div className="h-[70vh] overflow-hidden rounded-xl border border-slate-200">
              <LiveKitRoom
                token={activeJoin.credentials.token}
                serverUrl={activeJoin.credentials.ws_url}
                connect
                audio
                video
                data-lk-theme="default"
              >
                <VideoConference />
                <RoomAudioRenderer />
              </LiveKitRoom>
            </div>
          </section>
        )}
      </div>
    </div>
  );
};

export default VideoCallsPage;
