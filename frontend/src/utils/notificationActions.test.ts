import { describe, expect, it, vi } from "vitest";

import {
  extractNotificationActions,
  extractNotificationContext,
  formatNotificationAvailabilityLabel,
  getNotificationActionAvailability,
} from "./notificationActions";

describe("notificationActions utils", () => {
  it("extracts interview and case actions from metadata URLs", () => {
    const actions = extractNotificationActions({
      message: "Interview scheduled successfully.",
      metadata: {
        event_type: "interview_scheduled",
        interview_url: "/interview/interrogation/VET-12345",
        case_url: "/applications/VET-12345",
      },
    });

    expect(actions).toHaveLength(2);
    expect(actions[0]).toMatchObject({
      href: "/interview/interrogation/VET-12345",
      label: "Start interview",
      isExternal: false,
    });
    expect(actions[1]).toMatchObject({
      href: "/applications/VET-12345",
      label: "Open case",
      isExternal: false,
    });
  });

  it("keeps context fields readable while excluding URL metadata", () => {
    const context = extractNotificationContext({
      metadata: {
        case_id: "VET-20260306-ABC123",
        event_type: "interview_scheduled",
        interview_url: "/interview/interrogation/VET-20260306-ABC123",
        recommendation: "MANUAL_REVIEW",
      },
    });

    expect(context).toEqual(
      expect.arrayContaining([
        { label: "Case Id", value: "VET-20260306-ABC123" },
        { label: "Event Type", value: "interview_scheduled" },
        { label: "Recommendation", value: "MANUAL_REVIEW" },
      ]),
    );
    expect(context.find((field) => field.label === "Interview Url")).toBeUndefined();
  });

  it("marks join action as disabled when meeting is closed", () => {
    const [joinAction] = extractNotificationActions({
      message: "The call window has been closed.",
      metadata: {
        event_type: "video_call_time_up",
        meeting_url: "/video-calls?meeting=123",
        meeting_status: "completed",
      },
    });

    const availability = getNotificationActionAvailability(
      {
        message: "The call window has been closed.",
        metadata: {
          event_type: "video_call_time_up",
          meeting_url: "/video-calls?meeting=123",
          meeting_status: "completed",
        },
      },
      joinAction,
    );

    expect(availability.disabled).toBe(true);
    expect(availability.reason).toMatch(/closed/i);
  });

  it("keeps join action disabled until configured join window opens", () => {
    vi.useFakeTimers();
    try {
      vi.setSystemTime(new Date("2026-03-06T10:00:00Z"));

      const [joinAction] = extractNotificationActions({
        message: "Meeting starts soon.",
        metadata: {
          event_type: "video_call_scheduled",
          meeting_url: "/video-calls?meeting=123",
          meeting_status: "scheduled",
          scheduled_start: "2026-03-06T10:20:00Z",
          allow_join_before_seconds: 300,
        },
      });

      const availability = getNotificationActionAvailability(
        {
          message: "Meeting starts soon.",
          metadata: {
            event_type: "video_call_scheduled",
            meeting_url: "/video-calls?meeting=123",
            meeting_status: "scheduled",
            scheduled_start: "2026-03-06T10:20:00Z",
            allow_join_before_seconds: 300,
          },
        },
        joinAction,
      );

      expect(availability.disabled).toBe(true);
      expect(availability.reason).toMatch(/join will be available at/i);
      expect(availability.availableInMinutes).toBeGreaterThan(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("formats availability labels with adaptive duration units", () => {
    expect(formatNotificationAvailabilityLabel(5)).toBe("Available in 5m");
    expect(formatNotificationAvailabilityLabel(60)).toBe("Available in 1h");
    expect(formatNotificationAvailabilityLabel(125)).toBe("Available in 2h 5m");
  });
});
