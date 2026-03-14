// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import ReminderHealthCard from "./ReminderHealthCard";

const mocks = vi.hoisted(() => ({
  getReminderHealth: vi.fn(),
}));

vi.mock("@/services/videoCall.service", () => ({
  videoCallService: {
    getReminderHealth: mocks.getReminderHealth,
  },
}));

describe("ReminderHealthCard", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders a reminder trace link alongside health data", async () => {
    mocks.getReminderHealth.mockResolvedValue({
      generated_at: "2026-03-04T12:00:00Z",
      max_retries: 3,
      soon_retry_pending: 1,
      soon_retry_exhausted: 0,
      start_now_retry_pending: 0,
      start_now_retry_exhausted: 0,
      time_up_retry_pending: 0,
      time_up_retry_exhausted: 0,
    });

    render(
      <MemoryRouter>
        <ReminderHealthCard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.getReminderHealth).toHaveBeenCalledTimes(1);
    });

    expect(await screen.findByText("Reminder Runtime")).toBeTruthy();
    const traceLink = screen.getByRole("link", { name: /open reminder traces/i });
    expect(traceLink.getAttribute("href")).toBe(
      "/notifications?channel=all&event_type=video_call_reminder",
    );
    expect(
      screen.getByText(/review reminder-related notification delivery records/i),
    ).toBeTruthy();
  });
});
