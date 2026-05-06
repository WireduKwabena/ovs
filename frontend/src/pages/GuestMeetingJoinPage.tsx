import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Loader2, VideoOff } from "lucide-react";

import { videoCallService } from "@/services/videoCall.service";
import type { GuestMeetingJoinToken } from "@/types";

/**
 * Public join page for meeting participants who arrive via the personal
 * auto-join link embedded in their invitation email:
 *
 *   /join?t=<guest_token>&org=<org_slug>
 *
 * No login is required. The page exchanges the guest_token for a LiveKit
 * credential and immediately navigates to the full-screen MeetingRoomPage.
 */
const GuestMeetingJoinPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const guestToken = searchParams.get("t") ?? "";
  const orgSlug = searchParams.get("org") ?? "";

  const [error, setError] = useState<string | null>(null);
  const attemptedRef = useRef(false);

  useEffect(() => {
    if (attemptedRef.current) return;
    attemptedRef.current = true;

    if (!guestToken) {
      setError(
        "This join link is missing a required token. Please use the link from your invitation email.",
      );
      return;
    }

    (async () => {
      try {
        const data: GuestMeetingJoinToken = await videoCallService.guestJoin(
          guestToken,
          orgSlug,
        );

        // Navigate to the public guest room route; pass credentials so the
        // room page doesn't need to make another API call.
        navigate(`/join/room/${data.meeting_id}`, {
          replace: true,
          state: {
            credentials: {
              token: data.token,
              ws_url: data.ws_url,
              room_name: data.room_name,
              expires_in: data.expires_in,
            },
            // Minimal meeting info for the room header
            meeting: {
              id: data.meeting_id,
              title: data.meeting_title,
              livekit_room_name: data.room_name,
              scheduled_start: data.scheduled_start,
              scheduled_end: data.scheduled_end,
            },
          },
        });
      } catch (err: unknown) {
        const msg =
          (err as { response?: { data?: { error?: string; detail?: string } } })
            ?.response?.data?.error ??
          (err as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ??
          (err as { message?: string })?.message ??
          "Unable to join the meeting. The link may have expired or the meeting may have ended.";
        setError(msg);
      }
    })();
  }, [guestToken, orgSlug, navigate]);

  // ── Loading state ──────────────────────────────────────────────────────────
  if (!error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-neutral-950 text-white gap-4">
        <Loader2 className="h-10 w-10 animate-spin text-emerald-400" />
        <p className="text-sm text-neutral-400">Joining meeting…</p>
      </div>
    );
  }

  // ── Error state ────────────────────────────────────────────────────────────
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-neutral-950 text-white gap-6 px-4 text-center">
      <VideoOff className="h-12 w-12 text-rose-400" />
      <div className="space-y-2">
        <h1 className="text-xl font-semibold">Unable to join meeting</h1>
        <p className="text-sm text-neutral-400 max-w-sm">{error}</p>
      </div>
      <p className="text-xs text-neutral-600">
        If you believe this is an error, contact the meeting organiser for a new
        link.
      </p>
    </div>
  );
};

export default GuestMeetingJoinPage;
