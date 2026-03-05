// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

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

  it("renders healthy status when no retries are pending or exhausted", async () => {
    mocks.getReminderHealth.mockResolvedValue({
      generated_at: "2026-03-04T10:00:00.000Z",
      max_retries: 3,
      soon_retry_pending: 0,
      soon_retry_exhausted: 0,
      start_now_retry_pending: 0,
      start_now_retry_exhausted: 0,
      time_up_retry_pending: 0,
      time_up_retry_exhausted: 0,
    });

    const onStatusChange = vi.fn();
    render(<ReminderHealthCard onStatusChange={onStatusChange} />);

    await waitFor(() => {
      expect(mocks.getReminderHealth).toHaveBeenCalledTimes(1);
    });

    expect(await screen.findByText(/healthy/i)).toBeTruthy();
    expect(screen.getByText(/max retries configured/i)).toBeTruthy();
    expect(onStatusChange).toHaveBeenCalledWith("healthy");
  });

  it("renders attention status when retry queues are non-zero", async () => {
    mocks.getReminderHealth.mockResolvedValue({
      generated_at: "2026-03-04T10:00:00.000Z",
      max_retries: 3,
      soon_retry_pending: 1,
      soon_retry_exhausted: 0,
      start_now_retry_pending: 0,
      start_now_retry_exhausted: 2,
      time_up_retry_pending: 0,
      time_up_retry_exhausted: 0,
    });

    render(<ReminderHealthCard />);

    await waitFor(() => {
      expect(mocks.getReminderHealth).toHaveBeenCalledTimes(1);
    });

    expect(await screen.findByText(/attention needed/i)).toBeTruthy();
    expect(screen.getByText("1")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
  });

  it("shows unavailable state and error banner when fetch fails", async () => {
    mocks.getReminderHealth.mockRejectedValue(new Error("Request failed"));

    const onStatusChange = vi.fn();
    render(<ReminderHealthCard onStatusChange={onStatusChange} />);

    await waitFor(() => {
      expect(mocks.getReminderHealth).toHaveBeenCalledTimes(1);
    });

    expect(await screen.findByText(/unavailable/i)).toBeTruthy();
    expect(screen.getByText(/request failed/i)).toBeTruthy();
    expect(onStatusChange).toHaveBeenCalledWith("unavailable");
  });

  it("supports manual refresh", async () => {
    mocks.getReminderHealth
      .mockResolvedValueOnce({
        generated_at: "2026-03-04T10:00:00.000Z",
        max_retries: 3,
        soon_retry_pending: 0,
        soon_retry_exhausted: 0,
        start_now_retry_pending: 0,
        start_now_retry_exhausted: 0,
        time_up_retry_pending: 0,
        time_up_retry_exhausted: 0,
      })
      .mockResolvedValueOnce({
        generated_at: "2026-03-04T10:01:00.000Z",
        max_retries: 3,
        soon_retry_pending: 0,
        soon_retry_exhausted: 1,
        start_now_retry_pending: 0,
        start_now_retry_exhausted: 0,
        time_up_retry_pending: 0,
        time_up_retry_exhausted: 0,
      });

    render(<ReminderHealthCard />);

    await waitFor(() => {
      expect(mocks.getReminderHealth).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole("button", { name: /refresh/i }));

    await waitFor(() => {
      expect(mocks.getReminderHealth).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByText(/attention needed/i)).toBeTruthy();
  });
});
