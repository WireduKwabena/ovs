// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { NotificationDetailPage } from "./NotificationDetailPage";

const mocks = vi.hoisted(() => ({
  getById: vi.fn(),
  markSingleAsRead: vi.fn(),
  archive: vi.fn(),
  restore: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/services/notification.service", () => ({
  notificationService: {
    getById: mocks.getById,
    markSingleAsRead: mocks.markSingleAsRead,
    archive: mocks.archive,
    restore: mocks.restore,
  },
}));

vi.mock("react-toastify", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
  },
}));

const renderPage = (initialPath: string) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/notifications/:notificationId" element={<NotificationDetailPage />} />
          <Route path="/notifications" element={<div>Notifications list</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe("NotificationDetailPage archive controls", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows Delete for active notification and archives it", async () => {
    mocks.getById.mockResolvedValue({
      id: "notif-1",
      notification_type: "in_app",
      title: "Interview session scheduled",
      message: "Please join the interview.",
      status: "read",
      metadata: {},
      is_read: true,
      is_archived: false,
      created_at: "2026-03-06T10:00:00Z",
    });
    mocks.archive.mockResolvedValue(undefined);

    renderPage("/notifications/notif-1");

    const deleteButton = await screen.findByRole("button", { name: /delete/i });
    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(mocks.archive).toHaveBeenCalledWith("notif-1");
    });
    expect(await screen.findByText("Notifications list")).toBeTruthy();
  });

  it("shows Restore for archived notification and restores it", async () => {
    mocks.getById.mockResolvedValue({
      id: "notif-2",
      notification_type: "in_app",
      title: "Archived notification",
      message: "This has been archived.",
      status: "read",
      metadata: {},
      is_read: true,
      is_archived: true,
      created_at: "2026-03-06T10:00:00Z",
      archived_at: "2026-03-06T11:00:00Z",
    });
    mocks.restore.mockResolvedValue(undefined);

    renderPage("/notifications/notif-2");

    expect(await screen.findByText(/^Archived$/i)).toBeTruthy();
    const restoreButton = await screen.findByRole("button", { name: /restore/i });
    fireEvent.click(restoreButton);

    await waitFor(() => {
      expect(mocks.restore).toHaveBeenCalledWith("notif-2");
    });
    expect(screen.queryByRole("button", { name: /delete/i })).toBeNull();
  });

  it("linkifies URLs inside message text", async () => {
    mocks.getById.mockResolvedValue({
      id: "notif-3",
      notification_type: "in_app",
      title: "Useful links",
      message: "Open docs at https://example.com/docs?ref=notif for details.",
      status: "read",
      metadata: {},
      is_read: true,
      is_archived: false,
      created_at: "2026-03-06T10:00:00Z",
    });

    renderPage("/notifications/notif-3");

    const link = await screen.findByRole("link", {
      name: /https:\/\/example\.com\/docs\?ref=notif/i,
    });
    expect(link.getAttribute("href")).toBe("https://example.com/docs?ref=notif");
  });

  it("disables join action when meeting has already closed", async () => {
    mocks.getById.mockResolvedValue({
      id: "notif-4",
      notification_type: "in_app",
      title: "Meeting ended",
      message: "The scheduled meeting time is up. The call window has been closed.",
      status: "read",
      metadata: {
        event_type: "video_call_time_up",
        meeting_url: "/video-calls?meeting=abc",
        meeting_status: "completed",
        scheduled_start: "2026-03-06T09:00:00Z",
        scheduled_end: "2026-03-06T10:00:00Z",
      },
      is_read: true,
      is_archived: false,
      created_at: "2026-03-06T10:00:00Z",
    });

    renderPage("/notifications/notif-4");

    const joinButton = await screen.findByRole("button", { name: /join/i });
    expect(joinButton.hasAttribute("disabled")).toBe(true);
    expect(await screen.findByText(/meeting is closed/i)).toBeTruthy();
  });

  it("disables join action until meeting join window opens", async () => {
    mocks.getById.mockResolvedValue({
      id: "notif-5",
      notification_type: "in_app",
      title: "Meeting starts soon",
      message: "Please wait for meeting join window.",
      status: "read",
      metadata: {
        event_type: "video_call_scheduled",
        meeting_url: "/video-calls?meeting=future-abc",
        meeting_status: "scheduled",
        scheduled_start: "2099-01-01T10:20:00Z",
        allow_join_before_seconds: 300,
      },
      is_read: true,
      is_archived: false,
      created_at: "2099-01-01T10:00:00Z",
    });

    renderPage("/notifications/notif-5");

    const joinButton = await screen.findByRole("button", { name: /join/i });
    expect(joinButton.hasAttribute("disabled")).toBe(true);
    const title = joinButton.getAttribute("title") ?? "";
    expect(title).toMatch(/join will be available at/i);
    expect(
      await screen.findByText(/available in (\d+m|\d+h(?: \d+m)?)/i),
    ).toBeTruthy();
  });
});
