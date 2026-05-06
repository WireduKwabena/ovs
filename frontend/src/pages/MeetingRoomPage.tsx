import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  VideoConference,
} from "@livekit/components-react";
import {
  Maximize2,
  Minimize2,
  PhoneOff,
  Users,
  Wifi,
  WifiOff,
} from "lucide-react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { videoCallService } from "@/services/videoCall.service";
import type { VideoMeeting, VideoMeetingJoinToken } from "@/types";
import { getWorkspacePath } from "@/utils/appPaths";

// ─── Types ────────────────────────────────────────────────────────────────────

interface RoomLocationState {
  meeting?: VideoMeeting;
  credentials?: VideoMeetingJoinToken;
}

// ─── Elapsed-time hook ────────────────────────────────────────────────────────

function useElapsed(startedAt: number): string {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [startedAt]);
  const h = Math.floor(elapsed / 3600);
  const m = Math.floor((elapsed % 3600) / 60);
  const s = elapsed % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

// ─── Component ────────────────────────────────────────────────────────────────

const MeetingRoomPage: React.FC = () => {
  const { meetingId } = useParams<{ meetingId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state ?? {}) as RoomLocationState;

  const [meeting, setMeeting] = useState<VideoMeeting | null>(
    state.meeting ?? null,
  );
  const [credentials, setCredentials] = useState<VideoMeetingJoinToken | null>(
    state.credentials ?? null,
  );
  const [loading, setLoading] = useState(!state.credentials);
  const [error, setError] = useState<string | null>(null);
  const [leaving, setLeaving] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [connected, setConnected] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const joinedAtRef = useRef(Date.now());
  const elapsed = useElapsed(joinedAtRef.current);

  // ── Fetch credentials if arriving via direct URL (page refresh, shared link)
  useEffect(() => {
    if (credentials || !meetingId) return;
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const [meetingData, creds] = await Promise.all([
          state.meeting
            ? Promise.resolve(state.meeting)
            : videoCallService.getById(meetingId),
          videoCallService.getJoinToken(meetingId),
        ]);
        if (!cancelled) {
          setMeeting(meetingData);
          setCredentials(creds);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to join meeting.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [meetingId, credentials, state.meeting]);

  // ── Fullscreen change listener
  useEffect(() => {
    const handler = () => {
      setIsFullscreen(document.fullscreenElement != null);
    };
    document.addEventListener("fullscreenchange", handler);
    return () => document.removeEventListener("fullscreenchange", handler);
  }, []);

  // ── Fullscreen toggle
  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      void rootRef.current?.requestFullscreen();
    } else {
      void document.exitFullscreen();
    }
  }, []);

  // ── Leave room
  const handleLeave = useCallback(async () => {
    if (leaving || !meetingId) return;
    setLeaving(true);
    try {
      await videoCallService.leave(meetingId);
    } catch {
      // best-effort — navigate regardless
    }
    if (document.fullscreenElement) {
      try {
        await document.exitFullscreen();
      } catch {
        // ignore
      }
    }
    navigate(getWorkspacePath("video-calls"), { replace: true });
  }, [leaving, meetingId, navigate]);

  // ─── Loading / error states ───────────────────────────────────────────────

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#111]">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-600 border-t-white" />
          <p className="text-sm text-slate-400">Connecting to meeting…</p>
        </div>
      </div>
    );
  }

  if (error || !credentials) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#111]">
        <div className="flex flex-col items-center gap-4 text-center">
          <WifiOff className="h-12 w-12 text-rose-500" />
          <p className="text-base font-semibold text-white">
            {error ?? "Could not load meeting credentials."}
          </p>
          <button
            type="button"
            onClick={() => navigate(getWorkspacePath("video-calls"))}
            className="mt-2 rounded-lg bg-slate-700 px-4 py-2 text-sm text-white hover:bg-slate-600"
          >
            Back to Meetings
          </button>
        </div>
      </div>
    );
  }

  // ─── Meeting room ─────────────────────────────────────────────────────────

  return (
    <div
      ref={rootRef}
      className="fixed inset-0 z-50 flex flex-col bg-[#111] text-white"
    >
      {/* ── Top bar ── */}
      <div className="flex shrink-0 items-center justify-between gap-4 bg-[#1c1c1c] px-4 py-2.5 shadow-md">
        <div className="flex min-w-0 items-center gap-3">
          {/* Connection indicator */}
          {connected ? (
            <Wifi className="h-4 w-4 shrink-0 text-emerald-400" />
          ) : (
            <WifiOff className="h-4 w-4 shrink-0 text-slate-500" />
          )}
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold leading-tight text-white">
              {meeting?.title ?? credentials.room_name}
            </p>
            <p className="truncate text-xs text-slate-400">
              {credentials.room_name}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          {/* Participant count placeholder */}
          <span className="flex items-center gap-1 rounded-full bg-slate-800 px-2.5 py-1 text-xs text-slate-300">
            <Users className="h-3.5 w-3.5" />
            {meeting?.participants?.length ?? 0}
          </span>

          {/* Elapsed */}
          <span className="rounded-full bg-slate-800 px-2.5 py-1 text-xs tabular-nums text-slate-300">
            {elapsed}
          </span>

          {/* Fullscreen */}
          <button
            type="button"
            aria-label={isFullscreen ? "Exit full screen" : "Enter full screen"}
            onClick={toggleFullscreen}
            className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-700 hover:text-white"
          >
            {isFullscreen ? (
              <Minimize2 className="h-4 w-4" />
            ) : (
              <Maximize2 className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>

      {/* ── LiveKit room (fills remaining height) ── */}
      <div className="relative min-h-0 flex-1">
        <LiveKitRoom
          token={credentials.token}
          serverUrl={credentials.ws_url}
          connect
          audio
          video
          data-lk-theme="default"
          onConnected={() => setConnected(true)}
          onDisconnected={() => setConnected(false)}
          style={{ height: "100%", background: "transparent" }}
        >
          <VideoConference />
          <RoomAudioRenderer />
        </LiveKitRoom>
      </div>

      {/* ── Bottom controls bar ── */}
      <div className="flex shrink-0 items-center justify-center gap-3 bg-[#1c1c1c] px-6 py-3 shadow-[0_-2px_12px_rgba(0,0,0,0.5)]">
        {/* Leave button */}
        <button
          type="button"
          onClick={() => void handleLeave()}
          disabled={leaving}
          aria-label="Leave meeting"
          className="flex items-center gap-2 rounded-xl bg-rose-600 px-5 py-2.5 text-sm font-semibold text-white shadow transition hover:bg-rose-500 active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <PhoneOff className="h-4 w-4" />
          {leaving ? "Leaving…" : "Leave"}
        </button>

        {/* Fullscreen shortcut (bottom) */}
        <button
          type="button"
          aria-label={isFullscreen ? "Exit full screen" : "Enter full screen"}
          onClick={toggleFullscreen}
          className="rounded-xl bg-slate-700 p-2.5 text-slate-300 transition hover:bg-slate-600 hover:text-white active:scale-95"
        >
          {isFullscreen ? (
            <Minimize2 className="h-4 w-4" />
          ) : (
            <Maximize2 className="h-4 w-4" />
          )}
        </button>
      </div>
    </div>
  );
};

export default MeetingRoomPage;
