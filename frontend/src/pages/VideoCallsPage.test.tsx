// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import VideoCallsPage from "./VideoCallsPage";

const authHookState = vi.hoisted(() => ({
  isInternalOrAdmin: true,
  isAdmin: true,
  user: {
    id: "user-1",
    email: "hr@example.com",
  },
}));

const serviceMocks = vi.hoisted(() => ({
  list: vi.fn(),
  getAllCases: vi.fn(),
}));

vi.mock("@livekit/components-react", () => ({
  LiveKitRoom: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  RoomAudioRenderer: () => <div />,
  VideoConference: () => <div>Mock Conference</div>,
}));

vi.mock("react-toastify", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
  },
}));

vi.mock("@/components/admin/ReminderHealthCard", () => ({
  default: () => <div>Mock Reminder Runtime</div>,
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => authHookState,
}));

vi.mock("@/services/application.service", () => ({
  applicationService: {
    getAll: serviceMocks.getAllCases,
  },
}));

vi.mock("@/services/videoCall.service", () => ({
  videoCallService: {
    list: serviceMocks.list,
  },
}));

const scheduledMeeting = {
  id: "meeting-1",
  title: "Budget Review Interview",
  description: "Panel vetting session",
  scheduled_start: "2026-03-10T10:00:00Z",
  scheduled_end: "2026-03-10T11:00:00Z",
  timezone: "UTC",
  livekit_room_name: "room-budget-review",
  reminder_before_minutes: 15,
  status: "scheduled",
  participants: [
    {
      id: "participant-1",
      user_full_name: "Jane Doe",
      role: "candidate",
    },
  ],
} as const;

describe("VideoCallsPage layout regression", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    authHookState.isInternalOrAdmin = true;
    authHookState.isAdmin = true;
    authHookState.user = {
      id: "user-1",
      email: "hr@example.com",
    };
  });

  it("keeps the meeting action cluster in xl-only inline mode", async () => {
    serviceMocks.list.mockResolvedValue([scheduledMeeting]);
    serviceMocks.getAllCases.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <VideoCallsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(serviceMocks.list).toHaveBeenCalledTimes(1);
    });

    const actionCluster = await screen.findByTestId("meeting-actions-meeting-1");

    expect(actionCluster.className).toContain("xl:w-auto");
    expect(actionCluster.className).toContain("xl:max-w-[27rem]");
    expect(screen.getByText("Meeting Actions")).toBeTruthy();
    expect(screen.getByText("Schedule Controls")).toBeTruthy();
  });

  it("uses a two-column reschedule grid before xl", async () => {
    serviceMocks.list.mockResolvedValue([scheduledMeeting]);
    serviceMocks.getAllCases.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <VideoCallsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(serviceMocks.list).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(await screen.findByRole("button", { name: /custom time/i }));

    const reschedulePanel = await screen.findByTestId("meeting-reschedule-panel-meeting-1");

    expect(reschedulePanel.className).toContain("md:grid-cols-2");
    expect(reschedulePanel.className).toContain("xl:grid-cols-3");
  });
});
