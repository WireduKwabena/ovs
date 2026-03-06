// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { NotificationsPage } from "./NotificationsPage";

const mocks = vi.hoisted(() => ({
  useNotifications: vi.fn(),
}));

vi.mock("@/hooks/useNotifications", () => ({
  useNotifications: mocks.useNotifications,
}));

const activeNotification = {
  id: "active-1",
  notification_type: "in_app",
  title: "Active update",
  message: "Active notification body",
  status: "unread",
  metadata: {},
  is_read: false,
  is_archived: false,
  created_at: "2026-03-06T10:00:00Z",
};

const archivedNotification = {
  id: "archived-1",
  notification_type: "in_app",
  title: "Archived update",
  message: "Archived notification body",
  status: "read",
  metadata: {},
  is_read: true,
  is_archived: true,
  created_at: "2026-03-06T10:00:00Z",
  archived_at: "2026-03-06T11:00:00Z",
};

const closedMeetingNotification = {
  id: "active-closed-1",
  notification_type: "in_app",
  title: "Meeting closed",
  message: "The scheduled meeting time is up. The call window has been closed.",
  status: "read",
  metadata: {
    event_type: "video_call_time_up",
    meeting_url: "/video-calls?meeting=abc",
    meeting_status: "completed",
    scheduled_start: "2026-03-06T10:00:00Z",
    scheduled_end: "2026-03-06T10:30:00Z",
  },
  is_read: true,
  is_archived: false,
  created_at: "2026-03-06T10:40:00Z",
};

const futureMeetingNotification = {
  id: "active-future-1",
  notification_type: "in_app",
  title: "Meeting starts soon",
  message: "Your meeting starts in 15 minutes.",
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
};

const activeState = {
  notifications: [activeNotification],
  isLoading: false,
  archiveAsync: vi.fn(),
  restoreAsync: vi.fn(),
  refresh: vi.fn(),
  markAllAsRead: vi.fn(),
  markAsRead: vi.fn(),
};

const archivedState = {
  notifications: [archivedNotification],
  isLoading: false,
  archiveAsync: vi.fn(),
  restoreAsync: vi.fn(),
  refresh: vi.fn(),
  markAllAsRead: vi.fn(),
  markAsRead: vi.fn(),
};

const activeClosedState = {
  notifications: [closedMeetingNotification],
  isLoading: false,
  archiveAsync: vi.fn(),
  restoreAsync: vi.fn(),
  refresh: vi.fn(),
  markAllAsRead: vi.fn(),
  markAsRead: vi.fn(),
};

const activeFutureState = {
  notifications: [futureMeetingNotification],
  isLoading: false,
  archiveAsync: vi.fn(),
  restoreAsync: vi.fn(),
  refresh: vi.fn(),
  markAllAsRead: vi.fn(),
  markAsRead: vi.fn(),
};

describe("NotificationsPage soft archive UX", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows Delete action on active list by default", async () => {
    mocks.useNotifications.mockImplementation(({ archived }: { archived: string }) =>
      archived === "archived" ? archivedState : activeState,
    );

    render(
      <MemoryRouter>
        <NotificationsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Active update")).toBeTruthy();
    expect(screen.getByRole("button", { name: /delete/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /restore/i })).toBeNull();
  });

  it("shows Restore action when archived tab is selected", async () => {
    mocks.useNotifications.mockImplementation(({ archived }: { archived: string }) =>
      archived === "archived" ? archivedState : activeState,
    );

    render(
      <MemoryRouter>
        <NotificationsPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: /archived/i }));

    expect(await screen.findByText("Archived update")).toBeTruthy();
    expect(screen.getByRole("button", { name: /restore/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^delete$/i })).toBeNull();
  });

  it("disables join action on closed meeting notifications", async () => {
    mocks.useNotifications.mockImplementation(({ archived }: { archived: string }) =>
      archived === "archived" ? archivedState : activeClosedState,
    );

    render(
      <MemoryRouter>
        <NotificationsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Meeting closed")).toBeTruthy();
    const joinButton = screen.getByRole("button", { name: /join/i });
    expect(joinButton.hasAttribute("disabled")).toBe(true);
  });

  it("disables join action before join window opens", async () => {
    mocks.useNotifications.mockImplementation(({ archived }: { archived: string }) =>
      archived === "archived" ? archivedState : activeFutureState,
    );

    render(
      <MemoryRouter>
        <NotificationsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Meeting starts soon")).toBeTruthy();
    const joinButton = screen.getByRole("button", { name: /join/i });
    expect(joinButton.hasAttribute("disabled")).toBe(true);
    const title = joinButton.getAttribute("title") ?? "";
    expect(title).toMatch(/join will be available at/i);
    expect(screen.getByText(/available in (\d+m|\d+h(?: \d+m)?)/i)).toBeTruthy();
  });
});
