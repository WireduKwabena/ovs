// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import OperationsDashboardPage from "./OperationsDashboardPage";

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  getDashboard: vi.fn(),
  useAuth: vi.fn(),
}));

vi.mock("@/services/campaign.service", () => ({
  campaignService: {
    list: mocks.list,
    getDashboard: mocks.getDashboard,
  },
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => mocks.useAuth(),
}));

vi.mock("@/components/admin/OperationsDashboardChartsSection", () => ({
  default: () => <div>Charts</div>,
}));

vi.mock("react-toastify", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

const renderOperationsDashboard = () =>
  render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <Routes>
        <Route path="/dashboard" element={<OperationsDashboardPage />} />
        <Route path="/government/appointments" element={<div>Operations Appointments Route</div>} />
        <Route path="/government/positions" element={<div>Operations Positions Route</div>} />
        <Route path="/government/personnel" element={<div>Operations Personnel Route</div>} />
      </Routes>
    </MemoryRouter>,
  );

describe("OperationsDashboardPage government quick actions", () => {
  const mockHrContext = () => {
    mocks.useAuth.mockReturnValue({
      user: {
        id: "user-1",
        email: "hr@example.com",
        first_name: "HR",
        last_name: "Manager",
        full_name: "Operations User",
        phone_number: "",
        profile_picture_url: "",
        avatar_url: "",
        date_of_birth: "",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      },
    });
    mocks.list.mockResolvedValue([]);
    mocks.getDashboard.mockResolvedValue({
      total_candidates: 0,
      invited: 0,
      registered: 0,
      in_progress: 0,
      completed: 0,
      reviewed: 0,
      approved: 0,
      rejected: 0,
      escalated: 0,
    });
  };

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("navigates to government appointments", async () => {
    mockHrContext();
    renderOperationsDashboard();
    fireEvent.click(await screen.findByRole("button", { name: /government appointments/i }));
    expect(await screen.findByText("Operations Appointments Route")).toBeTruthy();
  });

  it("navigates to government positions", async () => {
    mockHrContext();
    renderOperationsDashboard();
    fireEvent.click(await screen.findByRole("button", { name: /government position registry/i }));
    expect(await screen.findByText("Operations Positions Route")).toBeTruthy();
  });

  it("navigates to government personnel", async () => {
    mockHrContext();
    renderOperationsDashboard();
    fireEvent.click(await screen.findByRole("button", { name: /government personnel registry/i }));
    expect(await screen.findByText("Operations Personnel Route")).toBeTruthy();
  });
});

