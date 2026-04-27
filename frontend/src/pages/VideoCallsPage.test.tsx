// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
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
  create: vi.fn(),
  scheduleSeries: vi.fn(),
  getJoinToken: vi.fn(),
  leave: vi.fn(),
}));

vi.mock("@livekit/components-react", () => ({
  LiveKitRoom: ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  ),
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
    create: serviceMocks.create,
    scheduleSeries: serviceMocks.scheduleSeries,
    getJoinToken: serviceMocks.getJoinToken,
    leave: serviceMocks.leave,
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

const toDatetimeLocal = (value: Date): string => {
  const offset = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 16);
};

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

    const actionCluster = await screen.findByTestId(
      "meeting-actions-meeting-1",
    );

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

    fireEvent.click(
      await screen.findByRole("button", { name: /custom time/i }),
    );

    const reschedulePanel = await screen.findByTestId(
      "meeting-reschedule-panel-meeting-1",
    );

    expect(reschedulePanel.className).toContain("md:grid-cols-2");
    expect(reschedulePanel.className).toContain("xl:grid-cols-3");
  });

  it("schedules a near-future meeting from the form", async () => {
    const now = new Date();
    const start = new Date(now.getTime() + 30_000);
    const end = new Date(start.getTime() + 5 * 60_000);
    const startValue = toDatetimeLocal(start);
    const endValue = toDatetimeLocal(end);

    serviceMocks.list.mockResolvedValue([]);
    serviceMocks.getAllCases.mockResolvedValue([]);
    serviceMocks.create.mockResolvedValue({
      ...scheduledMeeting,
      id: "meeting-created",
      title: "30s Smoke Check",
      scheduled_start: new Date(startValue).toISOString(),
      scheduled_end: new Date(endValue).toISOString(),
    });

    render(
      <MemoryRouter>
        <VideoCallsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(serviceMocks.list).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByTitle("Meeting title"), {
      target: { value: "30s Smoke Check" },
    });

    const datetimeInputs = screen.getAllByDisplayValue("").filter((node) => {
      return (
        node.tagName.toLowerCase() === "input" &&
        (node as HTMLInputElement).type === "datetime-local"
      );
    }) as HTMLInputElement[];

    fireEvent.change(datetimeInputs[0], { target: { value: startValue } });
    fireEvent.change(datetimeInputs[1], { target: { value: endValue } });

    fireEvent.click(screen.getByRole("button", { name: /schedule meeting/i }));

    await waitFor(() => {
      expect(serviceMocks.create).toHaveBeenCalledTimes(1);
    });

    expect(serviceMocks.create).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "30s Smoke Check",
        scheduled_start: new Date(startValue).toISOString(),
        scheduled_end: new Date(endValue).toISOString(),
        timezone: "UTC",
        reminder_before_minutes: 15,
      }),
    );
  });

  it("opens the in-call room after join token resolves", async () => {
    serviceMocks.list.mockResolvedValue([scheduledMeeting]);
    serviceMocks.getAllCases.mockResolvedValue([]);
    serviceMocks.getJoinToken.mockResolvedValue({
      token: "test-token",
      ws_url: "wss://livekit.example.test",
      room_name: scheduledMeeting.livekit_room_name,
      expires_in: 3600,
    });

    render(
      <MemoryRouter>
        <VideoCallsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(serviceMocks.list).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(await screen.findByRole("button", { name: /^join$/i }));

    await waitFor(() => {
      expect(serviceMocks.getJoinToken).toHaveBeenCalledWith("meeting-1");
    });

    expect(
      await screen.findByText(/in call: budget review interview/i),
    ).toBeTruthy();
    expect(await screen.findByText(/room: room-budget-review/i)).toBeTruthy();
    expect(await screen.findByText("Mock Conference")).toBeTruthy();
  });
});
