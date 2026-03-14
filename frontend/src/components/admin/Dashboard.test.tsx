// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AdminDashboard } from "./Dashboard";

const mocks = vi.hoisted(() => ({
  getDashboard: vi.fn(),
}));

vi.mock("@/services/admin.service", () => ({
  adminService: {
    getDashboard: mocks.getDashboard,
  },
}));

vi.mock("@/components/admin/BillingHealthCard", () => ({
  default: () => <div>Billing Health</div>,
}));

vi.mock("@/components/admin/ReminderHealthCard", () => ({
  default: () => <div>Reminder Health</div>,
}));

const renderAdminDashboard = () =>
  render(
    <MemoryRouter initialEntries={["/admin/dashboard"]}>
      <Routes>
        <Route path="/admin/dashboard" element={<AdminDashboard />} />
        <Route path="/government/appointments" element={<div>Appointments Route</div>} />
        <Route path="/government/positions" element={<div>Positions Route</div>} />
        <Route path="/government/personnel" element={<div>Personnel Route</div>} />
      </Routes>
    </MemoryRouter>,
  );

describe("AdminDashboard government quick actions", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const buildDashboardPayload = () => ({
    total_applications: 8,
    pending: 2,
    under_review: 1,
    approved: 4,
    rejected: 1,
    recent_applications: [],
  });

  it("navigates to appointment registry", async () => {
    mocks.getDashboard.mockResolvedValue(buildDashboardPayload());

    renderAdminDashboard();

    fireEvent.click(await screen.findByRole("button", { name: /appointment registry/i }));
    expect(await screen.findByText("Appointments Route")).toBeTruthy();
  });

  it("navigates to position registry", async () => {
    mocks.getDashboard.mockResolvedValue(buildDashboardPayload());

    renderAdminDashboard();

    fireEvent.click(await screen.findByRole("button", { name: /position registry/i }));
    expect(await screen.findByText("Positions Route")).toBeTruthy();
  });

  it("navigates to personnel registry", async () => {
    mocks.getDashboard.mockResolvedValue(buildDashboardPayload());

    renderAdminDashboard();

    fireEvent.click(await screen.findByRole("button", { name: /personnel registry/i }));
    expect(await screen.findByText("Personnel Route")).toBeTruthy();
  });

  it("renders all government quick action buttons", async () => {
    mocks.getDashboard.mockResolvedValue({
      ...buildDashboardPayload(),
    });

    renderAdminDashboard();

    expect(await screen.findByRole("button", { name: /appointment registry/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /position registry/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /personnel registry/i })).toBeTruthy();
  });
});
